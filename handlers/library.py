"""Template Library Lambda — /api/library/* routes.

GET  /api/library              — List library templates (filterable)
GET  /api/library/{slug}       — Get full template by slug

Public endpoints — no auth required.
"""

import json
from utils.response import success, error, options_response
from config.database import get_session
from models.template_library import TemplateLibraryItem


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    qs = event.get("queryStringParameters") or {}

    if method == "OPTIONS":
        return options_response()

    if path == "/api/library" and method == "GET":
        return _list(qs)

    parts = path.rstrip("/").split("/")
    if len(parts) == 4 and parts[2] == "library" and method == "GET":
        return _get(parts[3])

    return error(404, "NOT_FOUND", "Route not found")


def _list(qs: dict):
    session = get_session()
    try:
        query = session.query(TemplateLibraryItem).filter_by(is_active=True)

        if qs.get("industry"):
            query = query.filter_by(industry=qs["industry"])
        if qs.get("purpose"):
            query = query.filter_by(purpose=qs["purpose"])
        if qs.get("tone"):
            query = query.filter_by(tone=qs["tone"])

        items = query.order_by(TemplateLibraryItem.name).all()
        return success(200, {
            "templates": [t.to_summary() for t in items],
            "total": len(items),
        })
    finally:
        session.close()


def _get(slug: str):
    session = get_session()
    try:
        item = session.query(TemplateLibraryItem).filter_by(slug=slug, is_active=True).first()
        if not item:
            return error(404, "NOT_FOUND", "Template not found")
        return success(200, {"template": item.to_dict()})
    finally:
        session.close()
