"""
Storage service — abstracts local file storage vs AWS S3.

Local (default):  files saved to /app/data/
AWS S3 (prod):    files uploaded to S3, returns presigned URL for download

Switch by setting AWS_ACCESS_KEY_ID and S3_BUCKET_NAME in .env.
S3 free tier: 5GB storage, 20,000 GET requests/month — more than enough.
"""
from __future__ import annotations
import os
import io
import tempfile
from app.core.config import settings


async def save_pdf(note_id: str, pdf_bytes: bytes) -> str:
    """
    Save PDF bytes. Returns file path (local) or presigned URL (S3).
    """
    if settings.use_s3:
        return await _upload_to_s3(
            key=f"notes/pdf/{note_id}.pdf",
            data=pdf_bytes,
            content_type="application/pdf",
        )
    else:
        return _save_local(f"data/note_{note_id}.pdf", pdf_bytes)


async def save_fhir(note_id: str, fhir_json: str) -> str:
    """
    Save FHIR JSON. Returns file path (local) or presigned URL (S3).
    """
    data = fhir_json.encode("utf-8")
    if settings.use_s3:
        return await _upload_to_s3(
            key=f"notes/fhir/{note_id}.json",
            data=data,
            content_type="application/json",
        )
    else:
        return _save_local(f"data/fhir_{note_id}.json", data)


def _save_local(path: str, data: bytes) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


async def _upload_to_s3(key: str, data: bytes, content_type: str) -> str:
    """
    Upload to S3 and return a presigned URL valid for 1 hour.
    Free tier: 5GB storage, 20K GET + 2K PUT requests/month.
    """
    import asyncio
    import boto3

    def _upload():
        s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
            # Server-side encryption — free, good practice
            ServerSideEncryption="AES256",
        )
        # Return presigned URL — expires in 1 hour
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
            ExpiresIn=3600,
        )
        return url

    return await asyncio.to_thread(_upload)


async def get_s3_url(key: str, expires_in: int = 3600) -> str | None:
    """Generate a presigned URL for an existing S3 object."""
    if not settings.use_s3:
        return None

    import asyncio
    import boto3

    def _get():
        s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )

    return await asyncio.to_thread(_get)
