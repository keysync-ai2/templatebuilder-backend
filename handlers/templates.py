"""Templates Lambda — /api/templates/* and /api/render/* routes.

GET    /api/templates         — List user's templates
POST   /api/templates         — Create template
GET    /api/templates/{id}    — Get template
PUT    /api/templates/{id}    — Update template
DELETE /api/templates/{id}    — Delete template
POST   /api/render            — Render template to HTML
POST   /api/render/export     — Render + upload to S3, return download URL
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from services.template_service import (
    create_template, get_template, list_templates,
    update_template, delete_template, render_template,
)
from services.s3_service import upload_export
from engine.schema import to_frontend_format


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

    # /api/render routes (no template ID needed)
    if path == "/api/render" and method == "POST":
        return _render(body)
    if path == "/api/render/export" and method == "POST":
        return _export(body, user_id)

    # /api/templates routes
    if path == "/api/templates" and method == "GET":
        return _list(user_id)
    if path == "/api/templates" and method == "POST":
        return _create(body, user_id)

    # /api/templates/{id}
    parts = path.rstrip("/").split("/")
    if len(parts) == 4 and parts[2] == "templates":
        template_id = parts[3]
        if method == "GET":
            return _get(template_id, user_id)
        if method == "PUT":
            return _update(template_id, user_id, body)
        if method == "DELETE":
            return _delete(template_id, user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _list(user_id: str):
    session = get_session()
    try:
        templates = list_templates(session, user_id)
        return success(200, {
            "templates": [
                {
                    "id": t.id, "name": t.name, "subject": t.subject,
                    "thumbnail_url": t.thumbnail_url,
                    "updated_at": t.updated_at.isoformat(),
                }
                for t in templates
            ]
        })
    finally:
        session.close()


def _create(body: dict, user_id: str):
    name = body.get("name", "Untitled")
    components = body.get("components", [])

    session = get_session()
    try:
        t = create_template(session, user_id, name, components)
        return success(201, {"id": t.id, "name": t.name})
    finally:
        session.close()


def _get(template_id: str, user_id: str):
    session = get_session()
    try:
        t = get_template(session, template_id, user_id)
        if not t:
            return error(404, "NOT_FOUND", "Template not found")
        # Convert stored components to frontend nested format
        frontend = to_frontend_format({"components": t.components or []})
        return success(200, {
            "id": t.id,
            "templateName": t.name,
            "templateSubject": t.subject or "",
            "components": frontend.get("components", []),
            "updated_at": t.updated_at.isoformat(),
        })
    finally:
        session.close()


def _update(template_id: str, user_id: str, body: dict):
    session = get_session()
    try:
        t = update_template(session, template_id, user_id, body)
        if not t:
            return error(404, "NOT_FOUND", "Template not found")
        return success(200, {"id": t.id, "name": t.name, "updated_at": t.updated_at.isoformat()})
    finally:
        session.close()


def _delete(template_id: str, user_id: str):
    session = get_session()
    try:
        deleted = delete_template(session, template_id, user_id)
        if not deleted:
            return error(404, "NOT_FOUND", "Template not found")
        return success(200, {"deleted": True})
    finally:
        session.close()


def _render(body: dict):
    template_data = body.get("template")
    if not template_data:
        return error(400, "VALIDATION_ERROR", "Missing 'template' in body")

    result = render_template(template_data)
    if "errors" in result:
        return error(400, "VALIDATION_ERROR", "; ".join(result["errors"]))
    return success(200, result)


def _export(body: dict, user_id: str):
    template_data = body.get("template")
    if not template_data:
        return error(400, "VALIDATION_ERROR", "Missing 'template' in body")

    result = render_template(template_data)
    if "errors" in result:
        return error(400, "VALIDATION_ERROR", "; ".join(result["errors"]))

    export = upload_export(user_id, result["html"])
    return success(200, {"url": export["url"], "size_bytes": result["size_bytes"]})
