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


def _enrich_history(conversation_history):
    """Enrich conversation history — ensure tool context is preserved.

    If assistant messages have summaries of what was suggested/created,
    those are already in the content. Just pass through.
    """
    if not conversation_history:
        return []

    enriched = []
    for msg in conversation_history:
        # Only include role and content (skip widgets, they're too large)
        enriched.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })
    return enriched


def chat(messages: list[dict], conversation_history: list[dict] | None = None, user_id: str = None) -> dict:
    """Send a chat message with all tools available.

    Args:
        messages: New messages [{role, content}]
        conversation_history: Prior messages for context
        user_id: For brand profile and suggestion lookups

    Returns:
        {"role": "assistant", "content": str, "widgets": list}
    """
    client = _get_client()
    builtin_tools, registry = _get_all_tools(user_id)

    # Combine built-in + MCP tools
    all_tools = builtin_tools + registry.get_openai_tools()

    # Build message chain
    all_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    all_messages += _enrich_history(conversation_history)
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

        choice = response.choices[0]
        message = choice.message

        if not message.tool_calls:
            # Final response
            content = message.content or ""
            if widgets and not content.strip():
                content = "Here are your template suggestions! Pick one to customize in the editor."

            # Build enriched content for DB storage (includes tool summaries)
            return {
                "role": "assistant",
                "content": content,
                "widgets": widgets,
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

            all_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
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
    }
