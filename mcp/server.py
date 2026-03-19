"""MCP Server for Email HTML Engine.

Implements the Model Context Protocol (MCP) over stdio transport.
Detachable — imports only from engine/, never from handlers/services/models.

Deployment modes:
  1. Embedded — ChatFunction Lambda calls handle_tool_call() in-process
  2. Standalone — python -m mcp.server (JSON-RPC over stdio)
  3. CLI — Direct function calls for testing

Usage (standalone):
    python -m mcp.server
"""

import json
import sys
import logging
from typing import Optional, Callable

# Engine imports only — no Lambda/DB/AWS dependencies
from engine import build_html, validate_tree, to_frontend_format
from engine.builder import add_component, remove_component, inject_preset
from mcp.tools import TOOLS

logger = logging.getLogger(__name__)

# Protocol constants
JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "email-engine"
SERVER_VERSION = "1.0.0"


class EmailEngineMCPServer:
    """MCP server wrapping the email HTML engine.

    Args:
        preset_loader: Optional async callable(preset_id) -> dict.
            When embedded in Lambda, loads preset JSON from S3.
            When standalone, can load from local files or S3.
            If None, preset tools return an error asking for configuration.
    """

    def __init__(self, preset_loader: Optional[Callable] = None):
        self.preset_loader = preset_loader
        self._presets_cache: dict = {}

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------

    def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """Route a tool call to the appropriate handler.

        Returns:
            dict with either result data or {"error": "message"}
        """
        handlers = {
            "build_email_html": self._build_html,
            "validate_template": self._validate,
            "list_presets": self._list_presets,
            "get_preset": self._get_preset,
            "inject_preset": self._inject_preset,
            "add_component": self._add_component,
            "remove_component": self._remove_component,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return handler(arguments)
        except Exception as e:
            logger.exception(f"Tool '{tool_name}' failed")
            return {"error": str(e)}

    def _build_html(self, args: dict) -> dict:
        template = args.get("template")
        if not template:
            return {"error": "Missing 'template' argument"}

        html = build_html(template)
        frontend_template = to_frontend_format(template)
        return {
            "html": html,
            "size_bytes": len(html.encode("utf-8")),
            "template": frontend_template,
        }

    def _validate(self, args: dict) -> dict:
        template = args.get("template")
        if not template:
            return {"error": "Missing 'template' argument"}

        errors = validate_tree(template)
        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _list_presets(self, args: dict) -> dict:
        if not self.preset_loader:
            return {"error": "Preset loader not configured"}

        category = args.get("category")
        # preset_loader should support listing — returns list of metadata dicts
        try:
            presets = self.preset_loader("__list__", category=category)
            return {"presets": presets}
        except Exception as e:
            return {"error": f"Failed to list presets: {e}"}

    def _get_preset(self, args: dict) -> dict:
        if not self.preset_loader:
            return {"error": "Preset loader not configured"}

        preset_id = args.get("preset_id")
        if not preset_id:
            return {"error": "Missing 'preset_id' argument"}

        try:
            preset = self.preset_loader(preset_id)
            return {"preset": preset}
        except Exception as e:
            return {"error": f"Failed to load preset '{preset_id}': {e}"}

    def _inject_preset(self, args: dict) -> dict:
        if not self.preset_loader:
            return {"error": "Preset loader not configured"}

        template = args.get("template")
        preset_id = args.get("preset_id")
        position = args.get("position", -1)
        customizations = args.get("customizations", {})

        if not template:
            return {"error": "Missing 'template' argument"}
        if not preset_id:
            return {"error": "Missing 'preset_id' argument"}

        try:
            preset_json = self.preset_loader(preset_id)
            if customizations:
                preset_json["customizations"] = customizations
            updated = inject_preset(template, preset_json, position)
            return {"template": to_frontend_format(updated)}
        except Exception as e:
            return {"error": f"Failed to inject preset: {e}"}

    def _add_component(self, args: dict) -> dict:
        template = args.get("template")
        parent_id = args.get("parent_id")
        component = args.get("component")
        position = args.get("position", -1)

        if not template:
            return {"error": "Missing 'template' argument"}
        if not component:
            return {"error": "Missing 'component' argument"}

        updated = add_component(template, parent_id, component, position)
        return {"template": to_frontend_format(updated)}

    def _remove_component(self, args: dict) -> dict:
        template = args.get("template")
        component_id = args.get("component_id")

        if not template:
            return {"error": "Missing 'template' argument"}
        if not component_id:
            return {"error": "Missing 'component_id' argument"}

        updated = remove_component(template, component_id)
        return {"template": to_frontend_format(updated)}

    # ------------------------------------------------------------------
    # MCP Protocol (JSON-RPC over stdio)
    # ------------------------------------------------------------------

    def _handle_request(self, request: dict) -> dict:
        """Handle a single JSON-RPC request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._jsonrpc_response(req_id, {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            })

        elif method == "notifications/initialized":
            # Client acknowledgment — no response needed
            return None

        elif method == "tools/list":
            return self._jsonrpc_response(req_id, {
                "tools": TOOLS,
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = self.handle_tool_call(tool_name, arguments)

            if "error" in result:
                return self._jsonrpc_response(req_id, {
                    "content": [
                        {"type": "text", "text": json.dumps(result)},
                    ],
                    "isError": True,
                })
            else:
                return self._jsonrpc_response(req_id, {
                    "content": [
                        {"type": "text", "text": json.dumps(result)},
                    ],
                })

        elif method == "ping":
            return self._jsonrpc_response(req_id, {})

        else:
            return self._jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    def _jsonrpc_response(self, req_id, result: dict) -> dict:
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": req_id,
            "result": result,
        }

    def _jsonrpc_error(self, req_id, code: int, message: str) -> dict:
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def run_stdio(self):
        """Run the MCP server over stdio (JSON-RPC, one message per line)."""
        logger.info(f"Starting {SERVER_NAME} v{SERVER_VERSION} on stdio")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                response = self._jsonrpc_error(None, -32700, f"Parse error: {e}")
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                continue

            response = self._handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()


def main():
    """Entry point for standalone MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,  # Logs go to stderr, protocol goes to stdout
    )
    server = EmailEngineMCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
