import boto3
from botocore.client import Config

from app.core.config import settings


class S3StorageAdapter:
    def __init__(self) -> None:
        self._bucket = settings.storage_bucket_name
        public_url = settings.storage_public_url or settings.storage_endpoint_url

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            config=Config(signature_version="s3v4"),
            region_name=settings.storage_region,
        )
        # Cliente separado para generar URLs presignadas con el hostname público.
        # En dev apunta a localhost:9000; en prod coincide con storage_endpoint_url.
        self._public_client = boto3.client(
            "s3",
            endpoint_url=public_url,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            config=Config(signature_version="s3v4"),
            region_name=settings.storage_region,
        )

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def get_url(self, key: str) -> str:
        return self._public_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=3600,
        )
