"""LLM API integration — prompt building, tool-call loop, and response parsing.

Uses OpenAI-compatible API format (works with DeepSeek, OpenAI, or any compatible provider).
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

SYSTEM_PROMPT = """You are an email template design assistant built into the Template Builder app.

## Your Primary Role
When a user asks to create an email, use the suggest_templates tool to generate 5 customized template suggestions. This is ALWAYS your first action for any email creation request.

## How suggest_templates Works
1. You analyze the user's request and extract structured content
2. Call suggest_templates with the extracted content
3. The system will: search for matching layouts, fetch relevant images, apply brand colors, and customize each template with your content
4. 5 fully customized templates are returned to the user

## What to Extract
When the user describes an email, extract:
- purpose: what kind of email (welcome, sale, newsletter, launch, event, etc.)
- headline: main heading text
- subtitle: supporting text below headline
- cta_text: call-to-action button text
- features: list of 3-4 feature/benefit names (for feature sections)
- body_text: any additional body copy
- company: company/brand name (from context or brand profile)
- tone: professional, casual, friendly, urgent, playful, minimal
- image_queries: 2-3 Unsplash search queries for relevant images (e.g., "fitness workout gym", "modern office team")

## Rules
1. ALWAYS call suggest_templates first for email creation requests
2. Extract as much content as possible from the user's message
3. For image_queries, think about what visuals would match the email's purpose and industry
4. If the user asks for changes to a suggestion, use build_email_html to modify it
5. Keep text responses brief — present the suggestions and let the user choose
6. For non-email questions, respond normally without tools

## Example
User: "Create a welcome email for my yoga studio called ZenFlow"
You should call suggest_templates with:
{
  "purpose": "welcome email for yoga studio",
  "headline": "Welcome to ZenFlow",
  "subtitle": "Find your balance. Transform your practice. Join our community.",
  "cta_text": "Book Your First Class",
  "features": ["Expert Instructors", "All Levels Welcome", "Flexible Schedule"],
  "body_text": "Start your yoga journey with us. New members get their first week free.",
  "company": "ZenFlow",
  "tone": "friendly",
  "image_queries": ["yoga class studio", "meditation peaceful", "wellness healthy lifestyle"]
}"""

# Suggest tool definition (separate from MCP tools)
SUGGEST_TOOL = {
    "type": "function",
    "function": {
        "name": "suggest_templates",
        "description": (
            "Generate 5 customized email template suggestions. Extracts content from the user's request, "
            "finds matching template layouts via semantic search, fetches relevant Unsplash images, "
            "applies brand colors, and injects the content into each template. "
            "Returns 5 fully customized templates for the user to choose from."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "purpose": {
                    "type": "string",
                    "description": "What kind of email: welcome, sale, newsletter, launch, event, re-engagement, thank-you, etc.",
                },
                "headline": {
                    "type": "string",
                    "description": "Main heading text for the email hero section.",
                },
                "subtitle": {
                    "type": "string",
                    "description": "Supporting text below the headline.",
                },
                "cta_text": {
                    "type": "string",
                    "description": "Call-to-action button text.",
                },
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of 3-4 feature or benefit names for feature sections.",
                },
                "body_text": {
                    "type": "string",
                    "description": "Additional body copy or description text.",
                },
                "company": {
                    "type": "string",
                    "description": "Company or brand name.",
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "casual", "friendly", "urgent", "playful", "minimal"],
                    "description": "Email tone/style.",
                },
                "image_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 Unsplash search queries for relevant images.",
                },
            },
            "required": ["purpose", "headline", "subtitle", "cta_text"],
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


def _convert_tools_to_openai_format() -> list[dict]:
    """Convert MCP tool definitions to OpenAI-compatible format + add suggest tool."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["inputSchema"],
            },
        }
        for tool in TOOLS
    ]
    tools.append(SUGGEST_TOOL)
    return tools


def chat(messages: list[dict], conversation_history: list[dict] | None = None, user_id: str = None) -> dict:
    """Send a chat message with email-engine tools + suggestion tool available.

    Args:
        messages: New messages [{role, content}]
        conversation_history: Prior messages for context
        user_id: For brand profile lookup in suggestions

    Returns:
        {"role": "assistant", "content": str, "widgets": list}
    """
    client = _get_client()
    mcp = _get_mcp_server()
    tools = _convert_tools_to_openai_format()

    all_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    all_messages += (conversation_history or []) + messages

    widgets = []
    max_iterations = 10

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=tools,
            messages=all_messages,
        )

        choice = response.choices[0]
        message = choice.message

        if message.tool_calls:
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

                # Handle suggest_templates
                if fn_name == "suggest_templates":
                    try:
                        from services.smart_suggest import generate_suggestions
                        suggestions, query_used = generate_suggestions(
                            user_id or "anonymous",
                            fn_args,
                        )

                        # Return suggestions as tool result
                        result_summary = {
                            "suggestions_count": len(suggestions),
                            "query_used": query_used,
                            "templates": [
                                {"slug": s["slug"], "name": s["name"], "score": s["score"]}
                                for s in suggestions
                            ],
                        }
                        all_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result_summary),
                        })

                        # Add suggestions as widget
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

                # Handle MCP tools
                try:
                    result = mcp.handle_tool_call(fn_name, fn_args)
                except Exception as e:
                    logger.warning(f"Tool call {fn_name} failed: {e}")
                    result = {"error": str(e)}

                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })

                # Capture template widgets
                if fn_name == "build_email_html" and "html" in result:
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
        else:
            content = message.content or ""
            if widgets and not content.strip():
                content = "Here are your template suggestions! Pick one to customize."
            return {
                "role": "assistant",
                "content": content,
                "widgets": widgets,
            }

    return {
        "role": "assistant",
        "content": "Here are your template suggestions!",
        "widgets": widgets,
    }
