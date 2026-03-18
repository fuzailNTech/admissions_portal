"""
Minimal S3 client for document/media storage.
Uses app.settings for bucket, region, and optional credentials.
"""
import urllib.parse
import boto3
from app import settings


def get_client():
    """Return a boto3 S3 client with current settings."""
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


def get_bucket():
    """Return the configured bucket name."""
    return settings.S3_BUCKET_NAME


def generate_presigned_put(key: str, expires_in: int = 3600) -> str:
    """Return a presigned URL for PUTting an object to the given key."""
    client = get_client()
    bucket = get_bucket()
    return client.generate_presigned_url(
        "put_object",
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
