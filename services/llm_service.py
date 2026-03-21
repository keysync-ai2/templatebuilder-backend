"""LLM API integration — tool-call loop with brand profile + suggestion tools.

Tools available to LLM:
- get_brand_profile: fetch user's brand (name, colors, industry, tone, features)
- suggest_templates: generate 5 customized template suggestions
- build_email_html + other MCP tools: build/modify templates directly
"""

import json
import logging
from openai import OpenAI
from config.settings import DEEPSEEK_API_KEY
from mcp.server import EmailEngineMCPServer
from mcp.tools import TOOLS
from services.template_saver import create_template_saver
from engine.presets import local_preset_loader

logger = logging.getLogger(__name__)

_client = None
_mcp_server = None

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"
MAX_TOKENS = 8192

SYSTEM_PROMPT = """You are an AI email template design assistant built into the Template Builder app.

## Your Capabilities
1. **Create email templates** — use suggest_templates to generate 5 customized suggestions
2. **Know the user's brand** — call get_brand_profile to get their company name, colors, industry, tone
3. **Build custom templates** — use build_email_html to create templates from scratch
4. **Answer questions** — help with email design, copywriting, best practices

## When to Use Tools
- User wants to CREATE an email → call get_brand_profile first (to know their brand), then call suggest_templates
- User asks about their BRAND → call get_brand_profile
- User wants to BUILD from scratch → call get_brand_profile, then build_email_html
- User asks a QUESTION → respond directly, no tools needed

## suggest_templates Tool
Pass the user's request as-is. The system will:
1. Search for matching template layouts (Pinecone semantic search)
2. Write customized content for each template slot using the brand profile
3. Fetch relevant images from Unsplash
4. Apply brand colors to all templates
5. Return 5 fully customized templates

## Important Rules
1. ALWAYS call get_brand_profile before suggest_templates or build_email_html — you need the brand context
2. When presenting suggestions, summarize what was customized (brand name, colors, industry-specific content)
3. Keep responses concise — the templates speak for themselves
4. If user wants to modify a suggestion, acknowledge which one and describe what you'd change
5. Remember what you suggested — refer back to previous suggestions by name/number in follow-ups"""

# ─── Tool Definitions ───

BRAND_TOOL = {
    "type": "function",
    "function": {
        "name": "get_brand_profile",
        "description": (
            "Fetch the user's brand profile including company name, tagline, logo URL, "
            "brand colors (primary/secondary), industry, tone of voice, website URL, and "
            "key features/services. Call this BEFORE creating any templates so you can "
            "personalize content with their brand. Also call when user asks about their brand."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

SUGGEST_TOOL = {
    "type": "function",
    "function": {
        "name": "suggest_templates",
        "description": (
            "Generate 5 customized email template suggestions. Pass the user's request — "
            "the system will find matching layouts via semantic search, write slot-specific "
            "content using the brand profile, fetch Unsplash images, and apply brand colors. "
            "Returns 5 fully customized templates the user can preview and choose from."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_request": {
                    "type": "string",
                    "description": "The user's email request exactly as they wrote it.",
                },
            },
            "required": ["user_request"],
        },
    },
}


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def _get_mcp_server():
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = EmailEngineMCPServer(
            template_saver=create_template_saver(user_id="chat-assistant"),
            preset_loader=local_preset_loader,
        )
    return _mcp_server


def _get_all_tools(user_id=None):
    """All tools: built-in (brand + suggest) + dynamic MCP tools from registry."""
    from services.tool_registry import ToolRegistry

    registry = ToolRegistry(user_id)
    registry.set_embedded_handler(_get_mcp_server().handle_tool_call)
    registry.load_tools()

    # Built-in tools (not from MCP servers)
    builtin = [BRAND_TOOL, SUGGEST_TOOL]

    return builtin, registry


def _build_context(conversation_id, conversation_history, user_id=None):
    """Build conversation context using rolling summary + last 5 pairs.

    Uses context_manager for smart history pruning within 20K token budget.
    """
    from services.context_manager import build_history
    return build_history(conversation_id, conversation_history, user_id)


def chat(messages: list[dict], conversation_history: list[dict] | None = None,
         user_id: str = None, conversation_id: str = None) -> dict:
    """Send a chat message with all tools available.

    Args:
        messages: New messages [{role, content}]
        conversation_history: Prior messages for context
        user_id: For brand profile, suggestions, token tracking
        conversation_id: For rolling summary storage

    Returns:
        {"role": "assistant", "content": str, "widgets": list, "token_usage": dict}
    """
    from services.token_tracker import check_limit, track_usage, get_usage
    from services.map_reduce import needs_map_reduce, summarize_large_response

    # Check daily token limit
    allowed, usage = check_limit(user_id or "anonymous")
    if not allowed:
        return {
            "role": "assistant",
            "content": "You've reached your daily token limit (2M tokens). Your limit resets at midnight.",
            "widgets": [],
            "token_usage": usage,
        }

    client = _get_client()
    builtin_tools, registry = _get_all_tools(user_id)
    all_tools = builtin_tools + registry.get_openai_tools()

    # Build message chain with rolling summary
    all_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    all_messages += _build_context(conversation_id, conversation_history, user_id)
    all_messages += messages

    widgets = []
    max_iterations = 10
    brand_cache = {}

    for iteration in range(max_iterations):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=all_tools if all_tools else None,
            messages=all_messages,
        )

        # Track token usage
        if response.usage and user_id:
            track_usage(user_id, response.usage.prompt_tokens, response.usage.completion_tokens)

        choice = response.choices[0]
        message = choice.message

        if not message.tool_calls:
            # Final response
            content = message.content or ""
            if widgets and not content.strip():
                content = "Here are your template suggestions! Pick one to customize in the editor."

            return {
                "role": "assistant",
                "content": content,
                "widgets": widgets,
                "token_usage": get_usage(user_id or "anonymous"),
            }

        # Process tool calls
        all_messages.append(message.model_dump())

        for tc in message.tool_calls:
            fn_name = tc.function.name

            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError as e:
                logger.warning(f"Malformed tool args for {fn_name}: {e}")
                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps({"error": f"Invalid arguments: {e}"}),
                })
                continue

            # ── get_brand_profile ──
            if fn_name == "get_brand_profile":
                try:
                    from services.smart_suggest import get_brand_context
                    brand = get_brand_context(user_id or "anonymous")
                    brand_cache["profile"] = brand

                    if brand:
                        result = {
                            "has_profile": True,
                            "company_name": brand.get("business_name", ""),
                            "tagline": brand.get("tagline", ""),
                            "industry": brand.get("industry", "other"),
                            "tone": brand.get("tone", "professional"),
                            "primary_color": brand.get("primary_color", "#2563EB"),
                            "secondary_color": brand.get("secondary_color", "#1E40AF"),
                            "website": brand.get("website_url", ""),
                            "logo_url": brand.get("logo_url", ""),
                            "features": brand.get("features", []),
                        }
                    else:
                        result = {
                            "has_profile": False,
                            "message": "No brand profile set. Ask the user to set up their brand at /brand page.",
                        }
                except Exception as e:
                    logger.warning(f"get_brand_profile failed: {e}")
                    result = {"error": str(e)}

                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })
                continue

            # ── suggest_templates ──
            if fn_name == "suggest_templates":
                try:
                    from services.smart_suggest import generate_suggestions
                    request_text = fn_args.get("user_request", "")
                    suggestions, query_used = generate_suggestions(
                        user_id or "anonymous",
                        request_text,
                    )

                    # Rich summary for LLM to write a natural response
                    brand = brand_cache.get("profile")
                    result_summary = {
                        "success": True,
                        "suggestions_count": len(suggestions),
                        "query_used": query_used,
                        "brand_applied": brand is not None,
                        "brand_name": brand.get("business_name", "") if brand else "",
                        "brand_colors": brand.get("primary_color", "") if brand else "",
                        "templates": [
                            {
                                "rank": i + 1,
                                "slug": s["slug"],
                                "name": s["name"],
                                "score": s["score"],
                                "industry": s["industry"],
                                "purpose": s["purpose"],
                                "sections": len(s.get("components", [])),
                            }
                            for i, s in enumerate(suggestions)
                        ],
                    }
                    all_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result_summary),
                    })

                    # Add widget
                    widgets.append({
                        "type": "suggestion-cards",
                        "data": {
                            "suggestions": suggestions,
                            "query": query_used,
                        },
                    })
                except Exception as e:
                    logger.exception(f"suggest_templates failed: {e}")
                    all_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"error": str(e)}),
                    })
                continue

            # ── All other tools — route via ToolRegistry ──
            result = registry.call_tool(fn_name, fn_args)

            # Check if tool response is too large for context
            result_json = json.dumps(result, default=str)
            is_large, est_tokens = needs_map_reduce(result_json)

            if is_large:
                # Save full response to conversation_documents and request permission
                doc_id = _save_large_response(conversation_id, task_id, fn_name, result, est_tokens)
                return {
                    "role": "assistant",
                    "content": "",
                    "widgets": [{
                        "type": "permission-request",
                        "data": {
                            "doc_id": doc_id,
                            "tool_name": fn_name,
                            "estimated_tokens": est_tokens,
                            "message": f"The response from **{fn_name}** is very large (~{est_tokens:,} tokens). I need to summarize it to continue the conversation.",
                        },
                    }],
                    "token_usage": get_usage(user_id or "anonymous"),
                    "needs_permission": True,
                    "pending_doc_id": doc_id,
                    "pending_tool_call_id": tc.id,
                    "pending_messages": all_messages,
                }
            else:
                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_json,
                })

            # Capture template widgets from build_email_html
            actual_name = fn_name.split(":")[-1] if ":" in fn_name else fn_name
            if actual_name == "build_email_html" and "html" in result:
                widget = {
                    "type": "template-builder",
                    "data": {
                        "title": result.get("template", {}).get("templateName", "Email Template"),
                        "description": "Click to open in the visual editor",
                        "html": result["html"],
                        "template": result.get("template"),
                    },
                }
                if "editor_link" in result:
                    widget["data"]["editor_link"] = result["editor_link"]
                    widget["data"]["template_id"] = result["template_id"]
                widgets.append(widget)

    # Max iterations reached
    return {
        "role": "assistant",
        "content": "I've processed your request. Here are the results!",
        "widgets": widgets,
        "token_usage": get_usage(user_id or "anonymous"),
    }


def _save_large_response(conversation_id, task_id, tool_name, result, est_tokens):
    """Save a large tool response to conversation_documents for later processing."""
    import uuid
    session = get_session()
    try:
        from sqlalchemy import text as sql_text
        doc_id = str(uuid.uuid4())
        session.execute(sql_text('''
            INSERT INTO conversation_documents (id, conversation_id, task_id, doc_type, tool_name, content, estimated_tokens)
            VALUES (:id, :conv, :task, 'tool_response', :tool, :content, :tokens)
        '''), {
            'id': doc_id,
            'conv': conversation_id or '',
            'task': task_id or '',
            'tool': tool_name,
            'content': json.dumps(result, default=str),
            'tokens': est_tokens,
        })
        session.commit()
        return doc_id
    except Exception as e:
        logger.error(f"Failed to save large response: {e}")
        return ""
    finally:
        session.close()


def resume_after_permission(doc_id, choice, user_id=None, status_callback=None):
    """Resume processing after user grants/denies permission for map-reduce.

    Args:
        doc_id: conversation_documents.id with the large response
        choice: "summarize" or "skip"
        user_id: for token tracking
        status_callback: fn(message) for progress updates

    Returns: {"content": str, "tool_result_for_llm": str}
    """
    from services.map_reduce import summarize_large_response
    from services.token_tracker import get_usage

    session = get_session()
    try:
        from sqlalchemy import text as sql_text
        r = session.execute(sql_text(
            'SELECT tool_name, content, estimated_tokens FROM conversation_documents WHERE id = :id'
        ), {'id': doc_id})
        row = r.fetchone()
        if not row:
            return {"content": "Document not found.", "tool_result_for_llm": ""}

        tool_name, content_json, est_tokens = row
        content = json.loads(content_json) if isinstance(content_json, str) else content_json

        if choice == "summarize":
            if status_callback:
                status_callback(f"Summarizing large response from {tool_name}...")

            # Map-reduce with progress
            from services.map_reduce import _split_chunks, _summarize_chunk, _reduce_summaries, CHUNK_SIZE, OVERLAP, estimate_tokens as est

            text = json.dumps(content, default=str)
            chunks = _split_chunks(text, CHUNK_SIZE, OVERLAP)
            total_chunks = len(chunks)

            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                if status_callback:
                    status_callback(f"Summarizing chunk {i+1}/{total_chunks}...")
                summary = _summarize_chunk(chunk, tool_name, i + 1, total_chunks)
                chunk_summaries.append(summary)

                if user_id:
                    from services.token_tracker import track_usage
                    track_usage(user_id, est(chunk), est(summary))

            if len(chunk_summaries) > 1:
                if status_callback:
                    status_callback("Combining summaries...")
                final = _reduce_summaries("\n\n".join(chunk_summaries), tool_name)
            else:
                final = chunk_summaries[0] if chunk_summaries else ""

            return {
                "content": f"I've summarized the response from {tool_name} (~{est_tokens:,} tokens → {est(final):,} tokens).",
                "tool_result_for_llm": final,
            }
        else:
            # Skip — return minimal metadata
            if isinstance(content, dict):
                meta_parts = []
                if "suggestions" in content:
                    meta_parts.append(f"{len(content['suggestions'])} suggestions returned")
                elif "templates" in content:
                    meta_parts.append(f"{len(content['templates'])} templates returned")
                else:
                    meta_parts.append(f"Response with {len(content)} keys")
                meta = ". ".join(meta_parts)
            else:
                meta = f"Response data ({est_tokens:,} tokens)"

            return {
                "content": f"Results from {tool_name} are ready — you can view them below.",
                "tool_result_for_llm": meta,
            }
    finally:
        session.close()
