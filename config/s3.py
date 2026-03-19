"""Boto3 S3 client + CloudFront signer configuration."""

import boto3
from config.settings import S3_BUCKET

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def upload_to_s3(key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to S3 and return the key."""
    get_s3_client().put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    return key


def get_from_s3(key: str) -> bytes:
    """Download an object from S3."""
    resp = get_s3_client().get_object(Bucket=S3_BUCKET, Key=key)
    return resp["Body"].read()


def delete_from_s3(key: str):
    """Delete an object from S3."""
    get_s3_client().delete_object(Bucket=S3_BUCKET, Key=key)


def generate_presigned_upload(key: str, content_type: str, expires_in: int = 300) -> dict:
    """Generate a presigned URL for client-side upload."""
    return get_s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_in,
    )
