"""Brand Profile Lambda — /api/brand/* routes.

POST /api/brand          — Create or update brand profile
GET  /api/brand          — Get brand profile
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from models.brand_profile import BrandProfile


VALID_INDUSTRIES = {"saas", "ecommerce", "health", "food", "education", "events", "real_estate", "agency", "other"}
VALID_TONES = {"professional", "casual", "friendly", "urgent", "playful", "minimal"}


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

    if path == "/api/brand" and method == "POST":
        return _upsert(body, user_id)
    if path == "/api/brand" and method == "GET":
        return _get(user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _upsert(body: dict, user_id: str):
    """Create or update brand profile."""
    business_name = (body.get("business_name") or "").strip()
    if not business_name:
        return error(400, "VALIDATION_ERROR", "business_name is required")

    industry = body.get("industry", "other")
    if industry not in VALID_INDUSTRIES:
        industry = "other"

    tone = body.get("tone", "professional")
    if tone not in VALID_TONES:
        tone = "professional"

    session = get_session()
    try:
        profile = session.query(BrandProfile).filter_by(user_id=user_id).first()
        created = False

        if not profile:
            profile = BrandProfile(user_id=user_id)
            session.add(profile)
            created = True

        profile.business_name = business_name
        profile.tagline = (body.get("tagline") or "").strip()
        profile.description = (body.get("description") or "").strip()
        profile.website_url = (body.get("website_url") or "").strip()
        profile.logo_url = (body.get("logo_url") or "").strip()
        profile.features = body.get("features") or []
        profile.primary_color = body.get("primary_color", "#2563EB")
        profile.secondary_color = body.get("secondary_color", "#1E40AF")
        profile.industry = industry
        profile.tone = tone

        session.commit()
        session.refresh(profile)

        return success(201 if created else 200, {
            "brand_profile": profile.to_dict(),
            "created": created,
        })
    finally:
        session.close()


def _get(user_id: str):
    """Get brand profile for authenticated user."""
    session = get_session()
    try:
        profile = session.query(BrandProfile).filter_by(user_id=user_id).first()
        if not profile:
            return success(200, {"brand_profile": None, "has_profile": False})
        return success(200, {"brand_profile": profile.to_dict(), "has_profile": True})
    finally:
        session.close()
