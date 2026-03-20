"""MCP Servers Lambda — /api/mcp-servers/* routes.

GET    /api/mcp-servers           — List user's MCP servers
POST   /api/mcp-servers           — Add new MCP server
PUT    /api/mcp-servers/{id}      — Update MCP server
DELETE /api/mcp-servers/{id}      — Remove MCP server
POST   /api/mcp-servers/{id}/test — Test connection
"""

import json
from datetime import datetime, timezone
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from models.mcp_server import MCPServer
from services.mcp_client import MCPClient


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    body = json.loads(event.get("body") or "{}")
    headers = event.get("headers") or {}

    if method == "OPTIONS":
        return options_response()

    payload = verify_token(headers)
    if not payload:
        return error(401, "UNAUTHORIZED", "Invalid or missing token")
    user_id = payload["sub"]

    if path == "/api/mcp-servers" and method == "GET":
        return _list(user_id)
    if path == "/api/mcp-servers" and method == "POST":
        return _create(body, user_id)

    parts = path.rstrip("/").split("/")

    # /api/mcp-servers/{id}/test
    if len(parts) == 5 and parts[3] == "test" and method == "POST":
        return _test(parts[3], user_id)
    if len(parts) == 5 and parts[4] == "test" and method == "POST":
        return _test(parts[3], user_id)

    # /api/mcp-servers/{id}
    if len(parts) == 4 and parts[2] == "mcp-servers":
        server_id = parts[3]
        if method == "PUT":
            return _update(server_id, user_id, body)
        if method == "DELETE":
            return _delete(server_id, user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _list(user_id: str):
    session = get_session()
    try:
        servers = session.query(MCPServer).filter(
            (MCPServer.user_id == user_id) | (MCPServer.is_system == True)
        ).order_by(MCPServer.is_system.desc(), MCPServer.name).all()
        return success(200, {
            "servers": [s.to_dict() for s in servers],
        })
    finally:
        session.close()


def _create(body: dict, user_id: str):
    name = (body.get("name") or "").strip()
    if not name:
        return error(400, "VALIDATION_ERROR", "name is required")

    transport = body.get("transport", "http")
    if transport not in ("http", "stdio", "embedded"):
        return error(400, "VALIDATION_ERROR", "transport must be http, stdio, or embedded")

    url = (body.get("url") or "").strip()
    if transport == "http" and not url:
        return error(400, "VALIDATION_ERROR", "url is required for HTTP transport")

    session = get_session()
    try:
        server = MCPServer(
            user_id=user_id,
            name=name,
            description=(body.get("description") or "").strip(),
            transport=transport,
            url=url,
            command=(body.get("command") or "").strip(),
            api_key=(body.get("api_key") or "").strip(),
            headers=body.get("headers") or {},
            is_system=False,
        )

        # Test connection and fetch tools
        if transport == "http" and url:
            try:
                client = MCPClient(url=url, api_key=server.api_key, headers=server.headers)
                test_result = client.test_connection()
                if test_result["connected"]:
                    server.tools_cache = test_result["tools"]
                    server.last_connected_at = datetime.now(timezone.utc)
            except Exception:
                pass  # Save anyway, user can test later

        session.add(server)
        session.commit()
        session.refresh(server)

        return success(201, {"server": server.to_dict()})
    finally:
        session.close()


def _update(server_id: str, user_id: str, body: dict):
    session = get_session()
    try:
        server = session.query(MCPServer).filter_by(id=server_id).first()
        if not server:
            return error(404, "NOT_FOUND", "Server not found")
        if server.user_id != user_id and not server.is_system:
            return error(403, "FORBIDDEN", "Cannot modify this server")

        for key in ("name", "description", "url", "command", "api_key", "is_enabled"):
            if key in body:
                setattr(server, key, body[key])
        if "headers" in body:
            server.headers = body["headers"]

        session.commit()
        session.refresh(server)
        return success(200, {"server": server.to_dict()})
    finally:
        session.close()


def _delete(server_id: str, user_id: str):
    session = get_session()
    try:
        server = session.query(MCPServer).filter_by(id=server_id).first()
        if not server:
            return error(404, "NOT_FOUND", "Server not found")
        if server.is_system:
            return error(403, "FORBIDDEN", "Cannot delete system server")
        if server.user_id != user_id:
            return error(403, "FORBIDDEN", "Cannot delete this server")

        session.delete(server)
        session.commit()
        return success(200, {"deleted": True})
    finally:
        session.close()


def _test(server_id: str, user_id: str):
    session = get_session()
    try:
        server = session.query(MCPServer).filter_by(id=server_id).first()
        if not server:
            return error(404, "NOT_FOUND", "Server not found")

        if server.transport == "embedded":
            from mcp.tools import TOOLS
            server.tools_cache = TOOLS
            server.last_connected_at = datetime.now(timezone.utc)
            session.commit()
            return success(200, {
                "connected": True,
                "tools_count": len(TOOLS),
                "tools": [{"name": t["name"], "description": t["description"][:100]} for t in TOOLS],
            })

        if server.transport == "http":
            client = MCPClient(url=server.url, api_key=server.api_key, headers=server.headers or {})
            result = client.test_connection()

            if result["connected"]:
                server.tools_cache = result["tools"]
                server.last_connected_at = datetime.now(timezone.utc)
                session.commit()

            return success(200, {
                "connected": result["connected"],
                "tools_count": result["tools_count"],
                "tools": [{"name": t.get("name"), "description": t.get("description", "")[:100]} for t in result["tools"]],
                "error": result.get("error"),
            })

        return error(400, "UNSUPPORTED", f"Transport {server.transport} not testable")
    finally:
        session.close()
