"""Tool Registry — dynamically loads tools from all connected MCP servers.

On each chat request:
1. Fetch all enabled MCP servers for the user (+ system servers)
2. Load tools from cache (or refresh from server)
3. Build OpenAI-format tool definitions
4. Route tool calls to the correct MCP server
"""

import json
import logging
from datetime import datetime, timezone

from config.database import get_session
from models.mcp_server import MCPServer
from services.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Manages tools from all connected MCP servers."""

    def __init__(self, user_id=None):
        self.user_id = user_id
        self.tool_map = {}       # tool_name → MCPServer record
        self.tools = []          # OpenAI-format tool definitions
        self._clients = {}       # server_id → MCPClient instance
        self._embedded_handler = None  # For embedded email-engine

    def set_embedded_handler(self, handler_fn):
        """Set the embedded handler for the email-engine MCP server."""
        self._embedded_handler = handler_fn

    def load_tools(self):
        """Load tools from all enabled MCP servers."""
        session = get_session()
        try:
            # Fetch system servers + user's servers
            servers = session.query(MCPServer).filter(
                MCPServer.is_enabled == True,
                (MCPServer.user_id == self.user_id) | (MCPServer.user_id == None) | (MCPServer.is_system == True)
            ).all()

            for server in servers:
                try:
                    self._load_server_tools(server, session)
                except Exception as e:
                    logger.warning(f"Failed to load tools from {server.name}: {e}")
        finally:
            session.close()

    def _load_server_tools(self, server, session):
        """Load tools from a single MCP server."""
        # Use cached tools if available
        tools = server.tools_cache or []

        if not tools:
            # Fetch from server
            try:
                tools = self._fetch_tools(server)
                # Update cache in DB
                server.tools_cache = tools
                server.last_connected_at = datetime.now(timezone.utc)
                session.commit()
            except Exception as e:
                logger.warning(f"Cannot fetch tools from {server.name}: {e}")
                return

        # Register each tool
        for tool in tools:
            tool_name = tool.get("name", "")
            if not tool_name:
                continue

            # Handle name collisions with namespace
            registered_name = tool_name
            if tool_name in self.tool_map:
                registered_name = f"{server.name}:{tool_name}"

            self.tool_map[registered_name] = server

            self.tools.append({
                "type": "function",
                "function": {
                    "name": registered_name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {}),
                },
            })

    def _fetch_tools(self, server):
        """Fetch tools from an MCP server."""
        if server.transport == "embedded":
            # Embedded servers register tools directly
            from mcp.tools import TOOLS
            return TOOLS
        elif server.transport == "http":
            client = MCPClient(
                url=server.url,
                api_key=server.api_key,
                headers=server.headers or {},
            )
            return client.list_tools()
        else:
            logger.warning(f"Unsupported transport: {server.transport}")
            return []

    def get_openai_tools(self):
        """Return all tools in OpenAI function-calling format."""
        return self.tools

    def call_tool(self, tool_name, arguments):
        """Route a tool call to the correct MCP server and execute it."""
        server = self.tool_map.get(tool_name)
        if not server:
            return {"error": f"Unknown tool: {tool_name}"}

        # Strip namespace prefix for the actual call
        actual_name = tool_name
        if ":" in tool_name:
            actual_name = tool_name.split(":", 1)[1]

        try:
            if server.transport == "embedded":
                # Direct Python call
                if self._embedded_handler:
                    return self._embedded_handler(actual_name, arguments)
                return {"error": "Embedded handler not configured"}

            elif server.transport == "http":
                client = self._get_client(server)
                return client.call_tool(actual_name, arguments)

            else:
                return {"error": f"Unsupported transport: {server.transport}"}

        except Exception as e:
            logger.error(f"Tool call {tool_name} on {server.name} failed: {e}")
            return {"error": str(e)}

    def _get_client(self, server):
        """Get or create an MCPClient for a server."""
        if server.id not in self._clients:
            self._clients[server.id] = MCPClient(
                url=server.url,
                api_key=server.api_key,
                headers=server.headers or {},
            )
        return self._clients[server.id]
