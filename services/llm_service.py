"""DeepSeek API integration — prompt building, tool-call loop, and response parsing.

DeepSeek uses the OpenAI-compatible API format for chat completions and tool calling.
"""

import json
from openai import OpenAI
from config.settings import DEEPSEEK_API_KEY
from mcp.server import EmailEngineMCPServer
from mcp.tools import TOOLS

_client = None
_mcp_server = None

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"
MAX_TOKENS = 4096

SYSTEM_PROMPT = (
    "You are an email template design assistant. You help users create, edit, and refine "
    "email templates using the email-engine tools. When a user describes an email they want, "
    "generate the component tree JSON and use build_email_html to render it. Always validate "
    "templates before building. Keep responses concise."
)


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def _get_mcp_server():
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = EmailEngineMCPServer()
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
    while True:
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
                    "content": json.dumps(result),
                })

                # Capture rendered HTML + template JSON as a widget
                if fn_name == "build_email_html" and "html" in result:
                    widget = {
                        "type": "email_preview",
                        "html": result["html"],
                        "size_bytes": result.get("size_bytes", 0),
                    }
                    if "template" in result:
                        widget["template"] = result["template"]
                    widgets.append(widget)
        else:
            # No tool calls — final response
            return {
                "role": "assistant",
                "content": message.content or "",
                "widgets": widgets,
            }
