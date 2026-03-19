"""Images Lambda — /api/images/* routes.

GET    /api/images              — List user's images
POST   /api/images/presign      — Get presigned upload URL
DELETE /api/images/{id}         — Delete image
"""

import json
from utils.response import success, error, options_response
from utils.auth import verify_token
from config.database import get_session
from models.image import Image
from services.s3_service import get_upload_url, delete_image
from utils.cloudfront_signer import generate_signed_url


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

    if path == "/api/images" and method == "GET":
        return _list(user_id)
    if path == "/api/images/presign" and method == "POST":
        return _presign(body, user_id)

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
                    "url": generate_signed_url(img.s3_key),
                    "size_bytes": img.size_bytes,
                }
                for img in images
            ]
        })
    finally:
        session.close()


def _presign(body: dict, user_id: str):
    filename = body.get("filename", "")
    content_type = body.get("content_type", "image/png")

    if not filename:
        return error(400, "VALIDATION_ERROR", "filename is required")

    result = get_upload_url(user_id, filename, content_type)

    session = get_session()
    try:
        img = Image(
            user_id=user_id,
            s3_key=result["s3_key"],
            filename=filename,
            content_type=content_type,
        )
        session.add(img)
        session.commit()
        session.refresh(img)

        return success(200, {
            "image_id": img.id,
            "upload_url": result["upload_url"],
            "cdn_url": result["cdn_url"],
        })
    finally:
        session.close()


def _delete(image_id: str, user_id: str):
    session = get_session()
    try:
        img = session.query(Image).filter_by(id=image_id, user_id=user_id).first()
        if not img:
            return error(404, "NOT_FOUND", "Image not found")
        delete_image(img.s3_key)
        session.delete(img)
        session.commit()
        return success(200, {"deleted": True})
    finally:
        session.close()
