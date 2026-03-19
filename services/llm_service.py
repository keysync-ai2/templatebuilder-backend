"""LLM API integration — prompt building, tool-call loop, and response parsing.

Uses OpenAI-compatible API format (works with DeepSeek, OpenAI, or any compatible provider).
"""

import json
from openai import OpenAI
from config.settings import DEEPSEEK_API_KEY
from mcp.server import EmailEngineMCPServer
from mcp.tools import TOOLS
from services.template_saver import create_template_saver
from engine.presets import local_preset_loader

_client = None
_mcp_server = None

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"
MAX_TOKENS = 8192

SYSTEM_PROMPT = """You are an email template design assistant built into the Template Builder app.

## Your Role
Help users create, edit, and refine professional email templates. When a user describes an email they want, generate the full component tree JSON and use build_email_html to render it.

## Rules
1. ALWAYS use the build_email_html tool to generate templates — never describe templates without building them.
2. Build RICH templates with 5-8 rows minimum. Include hero, content sections, CTAs, and footer.
3. Every visual element must be a separate component. If you mention "3 feature cards", build a 3-column row.
4. Use multi-column rows (width: "50%" for 2-col, "33.33%" for 3-col) for side-by-side layouts.
5. After build_email_html returns, ALWAYS show the editor_link to the user so they can customize the template.
6. Keep text responses concise — the template speaks for itself.

## Available Presets
Call list_presets to see pre-built blocks you can inject instead of building from scratch.
Use inject_preset to compose emails from presets when they match the user's needs.

## Widget Format
When you generate a template, the tool returns HTML + an editor link. Present both to the user."""


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
    """Convert MCP tool definitions to OpenAI-compatible function tool format."""
    return [
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


def chat(messages: list[dict], conversation_history: list[dict] | None = None) -> dict:
    """Send a chat message with email-engine tools available.

    Args:
        messages: New messages [{role, content}]
        conversation_history: Prior messages for context

    Returns:
        {"role": "assistant", "content": str, "widgets": list}
    """
    client = _get_client()
    mcp = _get_mcp_server()
    tools = _convert_tools_to_openai_format()

    all_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    all_messages += (conversation_history or []) + messages

    # Agentic loop — handle tool calls until we get a final text response
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

        # Check for tool calls
        if message.tool_calls:
            # Append assistant message with tool calls
            all_messages.append(message.model_dump())

            for tc in message.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                result = mcp.handle_tool_call(fn_name, fn_args)

                # Append tool result
                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })

                # Capture rendered HTML + template as a widget
                if fn_name == "build_email_html" and "html" in result:
                    widget = {
                        "type": "template-builder",
                        "data": {
                            "title": result.get("template", {}).get("templateName", "Email Template"),
                            "description": "Click to open in the visual editor",
                            "timestamp": None,
                        },
                    }
                    # Add editor link if available
                    if "editor_link" in result:
                        widget["data"]["editor_link"] = result["editor_link"]
                        widget["data"]["template_id"] = result["template_id"]
                    # Add HTML preview
                    widget["data"]["html"] = result["html"]
                    widgets.append(widget)
        else:
            # No tool calls — final response
            content = message.content or ""

            # If we have widgets but no text, add a default message
            if widgets and not content.strip():
                content = "Here's your email template!"

            return {
                "role": "assistant",
                "content": content,
                "widgets": widgets,
            }

    # Safety: max iterations reached
    return {
        "role": "assistant",
        "content": "I've finished generating the template.",
        "widgets": widgets,
    }
