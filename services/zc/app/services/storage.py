import os
import hashlib
from typing import Optional, AsyncGenerator
import aiobotocore.session
from botocore.exceptions import ClientError

import logging

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.session = aiobotocore.session.get_session()
        self.bucket = os.getenv("S3_BUCKET", "wire-uploads")
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000") # Default MinIO
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
        self.region_name = os.getenv("AWS_REGION", "us-east-1")

    async def _create_client(self):
        return self.session.create_client(
            's3',
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )

    async def init_bucket(self):
        """Ensure the bucket exists."""
        async with await self._create_client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    await client.create_bucket(Bucket=self.bucket)
                    logger.info(f"Created S3 bucket {self.bucket}")
                else:
                    logger.error(f"S3 Error: {e}")
                    raise

    async def upload_stream(self, stream: AsyncGenerator[bytes, None], object_name: str) -> str:
        """Upload a stream to S3, returning the final etag/hash."""
        # For true stream uploads to S3, we would use multipart uploads.
        # Here we simulate by reading into memory or a temp file, 
        # or assuming the aiobotocore upload_fileobj supports it if we adapt it.
        # To keep it simple and robust, we'll collect chunks if it's small, 
        # or for large files we should implement the multipart API.
        
        # Simplified: collect into bytes (only for demonstration/small files in this implementation)
        data = bytearray()
        hasher = hashlib.blake2b()
        async for chunk in stream:
            data.extend(chunk)
            hasher.update(chunk)
            
        content_hash = hasher.hexdigest()
        # Content-addressable storage: prefix with hash
        key = f"objects/{content_hash}/{object_name}"
        
        async with await self._create_client() as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=bytes(data)
            )
            logger.info(f"Uploaded {key} to S3")
        return key

    async def get_object(self, key: str) -> bytes:
        """Retrieve an object from S3."""
        async with await self._create_client() as client:
            response = await client.get_object(Bucket=self.bucket, Key=key)
            async with response['Body'] as stream:
                return await stream.read()

storage_service = StorageService()
