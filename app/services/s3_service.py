import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()

LOCAL_STORAGE_DIR = Path("/tmp/local-s3-mock")


class S3Service:
    """
    S3 file storage service.
    Falls back to local filesystem storage when AWS credentials are not configured.
    """

    def __init__(self):
        if settings.s3_configured:
            self.client = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
            self.use_local = False
        else:
            self.client = None
            self.use_local = True
            LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def bucket(self) -> str:
        return settings.s3_bucket_name

    def _generate_key(self, prefix: str, filename: str) -> str:
        ext = Path(filename).suffix
        unique_name = f"{uuid.uuid4().hex}{ext}"
        return f"{prefix}/{unique_name}"

    async def upload_file(
        self,
        file_data: bytes,
        prefix: str,
        filename: str,
        content_type: str = "image/jpeg",
    ) -> str:
        """Upload file bytes. Returns the S3 key (or local path)."""
        key = self._generate_key(prefix, filename)

        if self.use_local:
            local_path = LOCAL_STORAGE_DIR / key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(file_data)
            return key

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_data,
            ContentType=content_type,
        )
        return key

    async def download_file(self, key: str) -> Optional[bytes]:
        """Download file by key. Returns bytes or None."""
        if self.use_local:
            local_path = LOCAL_STORAGE_DIR / key
            if local_path.exists():
                return local_path.read_bytes()
            return None

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError:
            return None

    async def generate_presigned_url(
        self, key: str, expiration: int = 3600
    ) -> Optional[str]:
        """Generate a presigned download URL. Returns local path in dev mode."""
        if self.use_local:
            local_path = LOCAL_STORAGE_DIR / key
            if local_path.exists():
                return f"/local-files/{key}"
            return None

        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiration,
            )
            return url
        except ClientError:
            return None

    async def delete_file(self, key: str) -> bool:
        """Delete a file by key."""
        if self.use_local:
            local_path = LOCAL_STORAGE_DIR / key
            if local_path.exists():
                local_path.unlink()
                return True
            return False

        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    async def file_exists(self, key: str) -> bool:
        """Check if a file exists."""
        if self.use_local:
            return (LOCAL_STORAGE_DIR / key).exists()

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


# Singleton instance
s3_service = S3Service()
