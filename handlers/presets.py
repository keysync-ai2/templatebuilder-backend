"""Presets Lambda — /api/presets/* routes.

GET  /api/presets             — List presets (optional ?category= filter)
GET  /api/presets/{id}        — Get preset with full component tree
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from services.preset_service import list_presets, get_preset


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    headers = event.get("headers") or {}
    qs = event.get("queryStringParameters") or {}

    if method == "OPTIONS":
        return options_response()

    payload = verify_token(headers)
    if not payload:
        return error(401, "UNAUTHORIZED", "Invalid or missing token")

    if path == "/api/presets" and method == "GET":
        return _list(qs.get("category"))

    parts = path.rstrip("/").split("/")
    if len(parts) == 4 and parts[2] == "presets" and method == "GET":
        return _get(parts[3])

    return error(404, "NOT_FOUND", "Route not found")


def _list(category: str | None):
    session = get_session()
    try:
        presets = list_presets(session, category)
        return success(200, {"presets": presets})
    finally:
        session.close()


def _get(preset_id: str):
    session = get_session()
    try:
        preset = get_preset(session, preset_id)
        if not preset:
            return error(404, "NOT_FOUND", "Preset not found")
        return success(200, preset)
    finally:
        session.close()
