import os
import io
import logging
from abc import ABC, abstractmethod
from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageService(ABC):
    @abstractmethod
    def upload_file(self, key: str, file_bytes: bytes, content_type: str = "application/pdf") -> str:
        """Uploads file bytes and returns the stored storage_key."""
        pass

    @abstractmethod
    def download_file(self, key: str) -> bytes:
        """Downloads file bytes given the storage_key."""
        pass

    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """Deletes file associated with the storage_key."""
        pass


class LocalStorageService(StorageService):
    def __init__(self, base_dir: str = settings.STORAGE_LOCAL_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_path(self, key: str) -> str:
        # Sanitize key to prevent path traversal
        safe_key = os.path.normpath(key).lstrip("\\/.")
        return os.path.join(self.base_dir, safe_key)

    def upload_file(self, key: str, file_bytes: bytes, content_type: str = "application/pdf") -> str:
        full_path = self._get_path(key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(file_bytes)
        logger.info(f"LocalStorageService: Uploaded {key} to {full_path}")
        return key

    def download_file(self, key: str) -> bytes:
        full_path = self._get_path(key)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Storage file not found: {key}")
        with open(full_path, "rb") as f:
            return f.read()

    def delete_file(self, key: str) -> bool:
        full_path = self._get_path(key)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False


class S3StorageService(StorageService):
    """S3-compatible storage service (AWS S3, Supabase Storage, Cloudflare R2)."""
    def __init__(self):
        import boto3
        from botocore.config import Config

        session = boto3.session.Session()
        client_kwargs = {
            "service_name": "s3",
            "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
            "region_name": settings.S3_REGION_NAME,
            "config": Config(s3={"addressing_style": "virtual"}),
        }
        if settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

        self.s3_client = session.client(**client_kwargs)
        self.bucket = settings.S3_BUCKET_NAME

    def upload_file(self, key: str, file_bytes: bytes, content_type: str = "application/pdf") -> str:
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        logger.info(f"S3StorageService: Uploaded {key} to bucket {self.bucket}")
        return key

    def download_file(self, key: str) -> bytes:
        response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete_file(self, key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete S3 object {key}: {e}")
            return False


def get_storage_service() -> StorageService:
    if settings.STORAGE_TYPE == "s3" and settings.S3_BUCKET_NAME:
        return S3StorageService()
    return LocalStorageService()
