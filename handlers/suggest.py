"""Suggest Lambda — /api/suggest routes.

POST /api/suggest         — Get top 5 template suggestions
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from models.brand_profile import BrandProfile
from models.template_library import TemplateLibraryItem
from services.suggestion import build_query, search_templates


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

    if path == "/api/suggest" and method == "POST":
        return _suggest(body, user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _suggest(body: dict, user_id: str):
    purpose = (body.get("purpose") or "").strip()
    if not purpose:
        return error(400, "VALIDATION_ERROR", "purpose is required")

    tone_override = body.get("tone_override")

    session = get_session()
    try:
        # Fetch brand profile
        brand = session.query(BrandProfile).filter_by(user_id=user_id).first()
        brand_dict = brand.to_dict() if brand else None

        # Build query
        query_text = build_query(purpose, brand_dict, tone_override)

        # Search Pinecone
        suggestions = search_templates(query_text, top_k=5)

        # Fetch full templates from DB
        slugs = [s["slug"] for s in suggestions]
        templates = session.query(TemplateLibraryItem).filter(
            TemplateLibraryItem.slug.in_(slugs),
            TemplateLibraryItem.is_active == True,
        ).all()

        template_map = {t.slug: t for t in templates}

        # Enrich suggestions with components
        results = []
        for s in suggestions:
            t = template_map.get(s["slug"])
            if t:
                results.append({
                    **s,
                    "components": t.components,
                })

        return success(200, {
            "suggestions": results,
            "query_used": query_text,
            "has_brand": brand_dict is not None,
        })
    finally:
        session.close()
