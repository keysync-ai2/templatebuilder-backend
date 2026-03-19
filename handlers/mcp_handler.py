"""MCP Lambda — /api/mcp endpoint.

MCP Streamable HTTP server for the email-engine tools.
Implements JSON-RPC protocol directly for Lambda (no ASGI/Mangum).

Reference: sample_mcp_tool.py (manage-logs MCP pattern)
"""

import json
from mcp.server import EmailEngineMCPServer
from mcp.tools import TOOLS

_mcp_server = None

SERVER_INFO = {
    "name": "email-engine",
    "version": "1.0.0",
}

PROTOCOL_VERSION = "2025-03-26"

_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, Mcp-Session-Id",
    "Access-Control-Allow-Methods": "POST, GET, DELETE, OPTIONS",
    "Access-Control-Expose-Headers": "Mcp-Session-Id",
    "Mcp-Session-Id": "lambda-stateless",
}


def _get_mcp_server():
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = EmailEngineMCPServer()
    return _mcp_server


def jsonrpc_response(req_id, result):
    return {
        "statusCode": 200,
        "headers": _HEADERS,
        "body": json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}),
    }


def jsonrpc_error(req_id, code, message):
    return {
        "statusCode": 200,
        "headers": _HEADERS,
        "body": json.dumps(
            {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
        ),
    }


def handler(event, context):
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")

    # CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": _HEADERS, "body": ""}

    # SSE — not supported in Lambda
    if method == "GET":
        return {"statusCode": 405, "headers": _HEADERS, "body": "SSE not supported in Lambda mode"}

    # Session termination — no-op for stateless Lambda
    if method == "DELETE":
        return {"statusCode": 200, "headers": _HEADERS, "body": ""}

    # Parse JSON-RPC request
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return jsonrpc_error(None, -32700, "Parse error")

    req_id = body.get("id")
    rpc_method = body.get("method")
    params = body.get("params", {})

    # ── initialize ──
    if rpc_method == "initialize":
        return jsonrpc_response(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })

    # ── notifications (no response needed, but Lambda must return something) ──
    if rpc_method == "notifications/initialized":
        return {"statusCode": 200, "headers": _HEADERS, "body": ""}

    # ── tools/list ──
    if rpc_method == "tools/list":
        return jsonrpc_response(req_id, {"tools": TOOLS})

    # ── tools/call ──
    if rpc_method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        mcp = _get_mcp_server()
        valid_names = {t["name"] for t in TOOLS}
        if tool_name not in valid_names:
            return jsonrpc_error(req_id, -32602, f"Unknown tool: {tool_name}")

        try:
            result = mcp.handle_tool_call(tool_name, arguments)
            if "error" in result:
                return jsonrpc_response(req_id, {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "isError": True,
                })
            return jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, default=str)}],
            })
        except Exception as e:
            return jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True,
            })

    # ── ping ──
    if rpc_method == "ping":
        return jsonrpc_response(req_id, {})

    return jsonrpc_error(req_id, -32601, f"Method not found: {rpc_method}")
