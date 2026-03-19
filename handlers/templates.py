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
from config.s3 import get_from_s3
from models.template import Template


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    body = json.loads(event.get("body") or "{}")
    headers = event.get("headers") or {}

    if method == "OPTIONS":
        return options_response()

    # Public route: /api/templates/public/{id} — no auth, for MCP-generated templates
    parts = path.rstrip("/").split("/")
    if len(parts) == 5 and parts[2] == "templates" and parts[3] == "public":
        template_id = parts[4]
        if method == "GET":
            return _get_public(template_id)
        return error(405, "METHOD_NOT_ALLOWED", "Only GET allowed")

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

        # If template has S3 key, load components from S3
        if t.s3_key:
            try:
                import json as _json
                s3_data = _json.loads(get_from_s3(t.s3_key))
                components = s3_data.get("components", [])
                template_name = s3_data.get("templateName", t.name)
                template_subject = s3_data.get("templateSubject", t.subject or "")
            except Exception:
                # Fallback to DB components if S3 fetch fails
                components = t.components or []
                template_name = t.name
                template_subject = t.subject or ""
        else:
            components = t.components or []
            template_name = t.name
            template_subject = t.subject or ""

        # Convert to frontend nested format
        frontend = to_frontend_format({"components": components})
        return success(200, {
            "id": t.id,
            "templateName": template_name,
            "templateSubject": template_subject,
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


def _get_public(template_id: str):
    """Get a template by ID without auth — for MCP-generated editor links."""
    session = get_session()
    try:
        t = session.query(Template).filter_by(id=template_id).first()
        if not t:
            return error(404, "NOT_FOUND", "Template not found")

        # Load from S3 if available
        if t.s3_key:
            try:
                import json as _json
                s3_data = _json.loads(get_from_s3(t.s3_key))
                components = s3_data.get("components", [])
                template_name = s3_data.get("templateName", t.name)
                template_subject = s3_data.get("templateSubject", t.subject or "")
            except Exception:
                components = t.components or []
                template_name = t.name
                template_subject = t.subject or ""
        else:
            components = t.components or []
            template_name = t.name
            template_subject = t.subject or ""

        frontend = to_frontend_format({"components": components})
        return success(200, {
            "id": t.id,
            "templateName": template_name,
            "templateSubject": template_subject,
            "components": frontend.get("components", []),
        })
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
