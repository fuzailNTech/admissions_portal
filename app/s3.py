"""
Minimal S3 client for document/media storage.
Uses app.settings for bucket, region, and optional credentials.
"""

import urllib.parse
import boto3
from app import settings
from botocore.config import Config


def get_client():
    """Return a boto3 S3 client with current settings."""
    kwargs = {"region_name": settings.AWS_REGION, "config": Config(signature_version="s3v4")}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


def get_bucket():
    """Return the configured bucket name."""
    return settings.S3_BUCKET_NAME


def generate_presigned_put(
    key: str, expires_in: int = 3600, content_type: str | None = None
) -> str:
    """Return a presigned URL for PUTting an object to the given key.
    If content_type is set, the client must send that exact Content-Type header when uploading.
    """
    client = get_client()
    bucket = get_bucket()
    params: dict = {"Bucket": bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    return client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires_in,
    )


def generate_presigned_get(key: str, expires_in: int = 300) -> str:
    """Return a presigned URL for GETting an object by key."""
    client = get_client()
    bucket = get_bucket()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def object_url(key: str) -> str:
    """Return the permanent URL for an object (for storing in DB / sending to client)."""
    bucket = get_bucket()
    if settings.S3_ENDPOINT_URL:
        base = settings.S3_ENDPOINT_URL.rstrip("/")
        return f"{base}/{bucket}/{urllib.parse.quote(key, safe='/')}"
    return f"https://{bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{urllib.parse.quote(key, safe='/')}"


def key_from_object_url_or_key(value: str | None) -> str | None:
    """
    Normalize a stored S3 reference into an object key.
    Accepts either:
    - raw key (preferred), e.g. students/<id>/profile/profile.png
    - full object URL, e.g. https://bucket.s3.region.amazonaws.com/students/<id>/...
    """
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    if "://" not in raw:
        return raw

    parsed = urllib.parse.urlparse(raw)
    path = urllib.parse.unquote(parsed.path or "").lstrip("/")
    bucket = get_bucket()
    if path.startswith(f"{bucket}/"):
        return path[len(bucket) + 1 :]
    return path


def build_presigned_get_from_object_url_or_key(value: str | None, expires_in: int = 300) -> str | None:
    """Build presigned GET URL from either a stored key or stored object URL."""
    key = key_from_object_url_or_key(value)
    if key is None:
        return None
    return generate_presigned_get(key, expires_in=expires_in)


def copy_object(source_key: str, dest_key: str) -> None:
    """Server-side copy within the same bucket."""
    client = get_client()
    bucket = get_bucket()
    client.copy_object(
        CopySource={"Bucket": bucket, "Key": source_key},
        Bucket=bucket,
        Key=dest_key,
    )


def delete_objects(keys: list[str]) -> None:
    """Delete one or more objects from the bucket. Silently ignores missing keys."""
    if not keys:
        return
    client = get_client()
    bucket = get_bucket()
    client.delete_objects(
        Bucket=bucket,
        Delete={"Objects": [{"Key": k} for k in keys]},
    )
