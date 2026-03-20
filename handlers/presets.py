"""Presets Lambda — /api/presets/* routes.

GET  /api/presets             — List presets (optional ?category= filter)
GET  /api/presets/{id}        — Get preset with full component tree

Public endpoints — no auth required (presets are shared resources).
"""

import json
from utils.response import success, error, options_response
from engine.presets import local_preset_loader


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    qs = event.get("queryStringParameters") or {}

    if method == "OPTIONS":
        return options_response()

    if path == "/api/presets" and method == "GET":
        return _list(qs.get("category"))

    parts = path.rstrip("/").split("/")
    if len(parts) == 4 and parts[2] == "presets" and method == "GET":
        return _get(parts[3])

    return error(404, "NOT_FOUND", "Route not found")


def _list(category: str | None):
    try:
        presets = local_preset_loader("__list__", category=category)
        return success(200, {"presets": presets})
    except Exception as e:
        return error(500, "INTERNAL_ERROR", str(e))


def _get(preset_id: str):
    try:
        preset = local_preset_loader(preset_id)
        return success(200, {"preset": preset})
    except ValueError as e:
        return error(404, "NOT_FOUND", str(e))
    except Exception as e:
        return error(500, "INTERNAL_ERROR", str(e))
