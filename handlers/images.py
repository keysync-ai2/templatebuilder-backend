"""Images Lambda — /api/images/* routes.

GET    /api/images              — List user's images
POST   /api/images/upload       — Upload image (base64)
DELETE /api/images/{id}         — Delete image
GET    /api/images/unsplash     — Search Unsplash (proxy)
"""

import json
import base64
import uuid
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from config.s3 import upload_to_s3, delete_from_s3
from config.settings import S3_BUCKET, CF_DISTRIBUTION_DOMAIN
from models.image import Image


UNSPLASH_API = "https://api.unsplash.com"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    body = json.loads(event.get("body") or "{}")
    headers = event.get("headers") or {}
    qs = event.get("queryStringParameters") or {}

    if method == "OPTIONS":
        return options_response()

    # Public: Unsplash proxy (no auth needed)
    if path == "/api/images/unsplash" and method == "GET":
        return _unsplash_search(qs)

    # Auth required for all other routes
    payload = verify_token(headers)
    if not payload:
        return error(401, "UNAUTHORIZED", "Invalid or missing token")
    user_id = payload["sub"]

    if path == "/api/images" and method == "GET":
        return _list(user_id)
    if path == "/api/images/upload" and method == "POST":
        return _upload(body, user_id)

    parts = path.rstrip("/").split("/")
    if len(parts) == 4 and parts[2] == "images" and method == "DELETE":
        return _delete(parts[3], user_id)

    return error(404, "NOT_FOUND", "Route not found")


def _list(user_id: str):
    session = get_session()
    try:
        images = session.query(Image).filter_by(user_id=user_id).order_by(Image.created_at.desc()).all()
        return success(200, {
            "images": [
                {
                    "id": img.id,
                    "filename": img.filename,
                    "url": _cdn_url(img.s3_key),
                    "size_bytes": img.size_bytes,
                    "created_at": img.created_at.isoformat() if img.created_at else None,
                }
                for img in images
            ]
        })
    finally:
        session.close()


def _upload(body: dict, user_id: str):
    """Upload base64-encoded image to S3."""
    data_str = body.get("data", "")  # base64 string (with or without data: prefix)
    filename = body.get("filename", "image.png")
    content_type = body.get("content_type", "image/png")

    if not data_str:
        return error(400, "VALIDATION_ERROR", "data (base64) is required")

    # Strip data URL prefix if present
    if "," in data_str:
        data_str = data_str.split(",", 1)[1]

    try:
        file_bytes = base64.b64decode(data_str)
    except Exception:
        return error(400, "VALIDATION_ERROR", "Invalid base64 data")

    if len(file_bytes) > MAX_FILE_SIZE:
        return error(413, "FILE_TOO_LARGE", "Image must be under 5MB")

    # Generate S3 key
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "png"
    s3_key = f"images/{user_id}/{uuid.uuid4().hex}.{ext}"

    # Upload to S3
    upload_to_s3(s3_key, file_bytes, content_type)

    # Save to DB
    session = get_session()
    try:
        img = Image(
            user_id=user_id,
            s3_key=s3_key,
            filename=filename,
            content_type=content_type,
            size_bytes=len(file_bytes),
        )
        session.add(img)
        session.commit()
        session.refresh(img)

        return success(201, {
            "id": img.id,
            "url": _cdn_url(s3_key),
            "filename": filename,
            "size_bytes": len(file_bytes),
        })
    finally:
        session.close()


def _delete(image_id: str, user_id: str):
    session = get_session()
    try:
        img = session.query(Image).filter_by(id=image_id, user_id=user_id).first()
        if not img:
            return error(404, "NOT_FOUND", "Image not found")
        try:
            delete_from_s3(img.s3_key)
        except Exception:
            pass  # S3 delete is best-effort
        session.delete(img)
        session.commit()
        return success(200, {"deleted": True})
    finally:
        session.close()


def _unsplash_search(qs: dict):
    """Proxy Unsplash search to hide API key."""
    import os
    try:
        from urllib.request import Request, urlopen
        from urllib.parse import urlencode
    except ImportError:
        return error(500, "INTERNAL_ERROR", "urllib not available")

    access_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if not access_key:
        return error(500, "NOT_CONFIGURED", "Unsplash API key not configured")

    query = qs.get("q", "")
    page = qs.get("page", "1")
    per_page = qs.get("per_page", "12")

    if query:
        url = f"{UNSPLASH_API}/search/photos?{urlencode({'query': query, 'page': page, 'per_page': per_page})}"
    else:
        url = f"{UNSPLASH_API}/photos?{urlencode({'page': page, 'per_page': per_page})}"

    req = Request(url, headers={"Authorization": f"Client-ID {access_key}"})

    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return error(502, "UPSTREAM_ERROR", f"Unsplash API error: {str(e)}")

    # Normalize response
    results = data.get("results", data) if isinstance(data, dict) else data
    images = []
    for img in (results if isinstance(results, list) else []):
        images.append({
            "id": img.get("id"),
            "url_small": img.get("urls", {}).get("small", ""),
            "url_regular": img.get("urls", {}).get("regular", ""),
            "url_full": img.get("urls", {}).get("full", ""),
            "alt": img.get("alt_description", ""),
            "photographer": img.get("user", {}).get("name", ""),
            "photographer_url": img.get("user", {}).get("links", {}).get("html", ""),
        })

    return success(200, {"images": images})


def _cdn_url(s3_key: str) -> str:
    """Generate CDN URL for an S3 key."""
    if CF_DISTRIBUTION_DOMAIN:
        return f"https://{CF_DISTRIBUTION_DOMAIN}/{s3_key}"
    # Fallback to direct S3 URL
    if S3_BUCKET:
        return f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"
    return s3_key
