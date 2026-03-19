"""S3 upload/download + CloudFront URL generation."""

import uuid
from config.s3 import upload_to_s3, get_from_s3, delete_from_s3, generate_presigned_upload
from utils.cloudfront_signer import generate_signed_url


def upload_image(user_id: str, filename: str, content_type: str, data: bytes) -> dict:
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "png"
    key = f"images/{user_id}/{uuid.uuid4().hex}.{ext}"
    upload_to_s3(key, data, content_type)
    url = generate_signed_url(key)
    return {"s3_key": key, "url": url}


def get_upload_url(user_id: str, filename: str, content_type: str) -> dict:
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "png"
    key = f"images/{user_id}/{uuid.uuid4().hex}.{ext}"
    presigned = generate_presigned_upload(key, content_type)
    cdn_url = generate_signed_url(key, expires_in=86400)
    return {"upload_url": presigned, "s3_key": key, "cdn_url": cdn_url}


def delete_image(s3_key: str):
    delete_from_s3(s3_key)


def upload_export(user_id: str, html: str) -> dict:
    key = f"exports/{user_id}/{uuid.uuid4().hex}.html"
    upload_to_s3(key, html.encode("utf-8"), "text/html")
    url = generate_signed_url(key, expires_in=3600)
    return {"s3_key": key, "url": url}
