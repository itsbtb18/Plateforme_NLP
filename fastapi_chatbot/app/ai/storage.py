from __future__ import annotations

import mimetypes
from urllib.parse import urlparse

import httpx

from app.config import get_settings

settings = get_settings()


class ObjectStorageService:
    """Storage abstraction for MinIO/S3 and signed URL handling."""

    def __init__(self) -> None:
        self.bucket = settings.AI_STORAGE_BUCKET

    def read_bytes(self, file_uri: str) -> tuple[bytes, str | None]:
        if file_uri.startswith("http://") or file_uri.startswith("https://"):
            return self._read_http(file_uri)
        if file_uri.startswith("s3://"):
            return self._read_s3(file_uri)
        raise ValueError("Unsupported URI scheme")

    def write_text_result(self, *, job_id: str, suffix: str, content: str) -> str | None:
        if not settings.AI_ENABLE_RESULT_STORAGE:
            return None
        key = f"ai-results/{job_id}/{suffix}.txt"
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.AI_S3_ENDPOINT,
                aws_access_key_id=settings.AI_S3_ACCESS_KEY,
                aws_secret_access_key=settings.AI_S3_SECRET_KEY,
                region_name=settings.AI_S3_REGION,
            )
            client.put_object(Bucket=self.bucket, Key=key, Body=content.encode("utf-8"), ContentType="text/plain")
            return f"s3://{self.bucket}/{key}"
        except Exception:
            return None

    def create_signed_get_url(self, uri: str, expires_seconds: int = 900) -> str:
        if not uri.startswith("s3://"):
            return uri

        parsed = urlparse(uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.AI_S3_ENDPOINT,
            aws_access_key_id=settings.AI_S3_ACCESS_KEY,
            aws_secret_access_key=settings.AI_S3_SECRET_KEY,
            region_name=settings.AI_S3_REGION,
        )
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )

    @staticmethod
    def validate_file(mime_type: str | None, filename: str | None, size_bytes: int | None) -> None:
        if size_bytes and size_bytes > settings.AI_MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError("File exceeds maximum allowed size")

        allowed = {".pdf", ".docx", ".pptx", ".txt", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
        if filename:
            lower = filename.lower()
            if not any(lower.endswith(ext) for ext in allowed):
                raise ValueError("Unsupported file extension")

        if mime_type and mime_type.startswith("application/x-msdownload"):
            raise ValueError("Forbidden MIME type")

    def _read_http(self, file_uri: str) -> tuple[bytes, str | None]:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(file_uri)
            response.raise_for_status()
            mime = response.headers.get("content-type")
            return response.content, mime

    def _read_s3(self, file_uri: str) -> tuple[bytes, str | None]:
        parsed = urlparse(file_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.AI_S3_ENDPOINT,
            aws_access_key_id=settings.AI_S3_ACCESS_KEY,
            aws_secret_access_key=settings.AI_S3_SECRET_KEY,
            region_name=settings.AI_S3_REGION,
        )
        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read()
        mime = obj.get("ContentType") or mimetypes.guess_type(key)[0]
        return body, mime


_storage: ObjectStorageService | None = None


def get_object_storage() -> ObjectStorageService:
    global _storage
    if _storage is None:
        _storage = ObjectStorageService()
    return _storage
