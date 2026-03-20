"""MCP Client — connect to any MCP server via HTTP and call tools.

Implements the MCP protocol (JSON-RPC 2.0) for:
- initialize: handshake with the server
- tools/list: discover available tools
- tools/call: execute a specific tool
"""

import json
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-03-26"


class MCPClient:
    """Connect to an MCP server and call tools via HTTP transport."""

    def __init__(self, url, api_key="", headers=None):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.custom_headers = headers or {}
        self._initialized = False
        self._req_id = 0

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    def _build_headers(self):
        h = {
            "Content-Type": "application/json",
            **self.custom_headers,
        }
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _send_jsonrpc(self, method, params=None, timeout=30):
        """Send a JSON-RPC request and return the result."""
        body = {
            "jsonrpc": JSONRPC_VERSION,
            "id": self._next_id(),
            "method": method,
        }
        if params:
            body["params"] = params

        data = json.dumps(body).encode("utf-8")
        req = Request(self.url, data=data, headers=self._build_headers(), method="POST")

        try:
            with urlopen(req, timeout=timeout) as resp:
                response = json.loads(resp.read())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            logger.error(f"MCP HTTP error {e.code}: {error_body[:200]}")
            raise ConnectionError(f"MCP server returned {e.code}: {error_body[:100]}")
        except URLError as e:
            logger.error(f"MCP connection error: {e}")
            raise ConnectionError(f"Cannot connect to MCP server: {e}")
        except Exception as e:
            logger.error(f"MCP request error: {e}")
            raise ConnectionError(f"MCP request failed: {e}")

        if "error" in response:
            err = response["error"]
            raise RuntimeError(f"MCP error {err.get('code', '?')}: {err.get('message', '?')}")

        return response.get("result", {})

    def initialize(self):
        """Initialize connection with the MCP server."""
        result = self._send_jsonrpc("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "template-builder", "version": "1.0.0"},
        })
        self._initialized = True
        return result

    def list_tools(self):
        """Fetch available tools from the MCP server.

        Returns list of tool dicts: [{name, description, inputSchema}]
        """
        if not self._initialized:
            try:
                self.initialize()
            except Exception:
                pass  # Some servers don't require initialization

        result = self._send_jsonrpc("tools/list")
        return result.get("tools", [])

    def call_tool(self, tool_name, arguments):
        """Call a tool on the MCP server.

        Returns the tool result (parsed from content array).
        """
        result = self._send_jsonrpc("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        # Parse MCP content format
        content = result.get("content", [])
        is_error = result.get("isError", False)

        # Extract text content
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))

        combined = "\n".join(texts)

        # Try to parse as JSON
        try:
            parsed = json.loads(combined)
            if is_error:
                return {"error": parsed.get("error", combined)}
            return parsed
        except (json.JSONDecodeError, TypeError):
            if is_error:
                return {"error": combined}
            return {"result": combined}

    def test_connection(self):
        """Test if the MCP server is reachable and responds.

        Returns: {connected: bool, tools_count: int, tools: [...], error: str}
        """
        try:
            self.initialize()
            tools = self.list_tools()
            return {
                "connected": True,
                "tools_count": len(tools),
                "tools": tools,
                "error": None,
            }
        except Exception as e:
            return {
                "connected": False,
                "tools_count": 0,
                "tools": [],
                "error": str(e),
            }
