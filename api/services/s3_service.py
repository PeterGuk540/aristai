"""S3 Service for Course Materials file operations."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple, BinaryIO

import boto3
from botocore.exceptions import ClientError

from api.core.config import get_settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for interacting with AWS S3 for course materials."""

    def __init__(self):
        settings = get_settings()
        self.bucket_name = settings.aws_s3_bucket_name
        self.region = settings.aws_region
        self.max_file_size_mb = settings.aws_s3_max_file_size_mb
        self.max_file_size_bytes = self.max_file_size_mb * 1024 * 1024

        # Initialize S3 client
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=self.region,
            )
            self.enabled = True
            logger.info(f"S3 service initialized with bucket: {self.bucket_name}")
        else:
            self.s3_client = None
            self.enabled = False
            logger.warning("S3 service disabled: AWS credentials not configured")

    def is_enabled(self) -> bool:
        """Check if S3 service is enabled."""
        return self.enabled

    def generate_s3_key(self, course_id: int, filename: str, session_id: Optional[int] = None) -> str:
        """
        Generate a unique S3 key for a file.

        Format: courses/{course_id}/materials/{session_id or 'general'}/{uuid}_{filename}
        """
        unique_id = uuid.uuid4().hex[:12]
        session_folder = f"session_{session_id}" if session_id else "general"
        safe_filename = filename.replace(" ", "_")
        return f"courses/{course_id}/materials/{session_folder}/{unique_id}_{safe_filename}"

    def upload_file(
        self,
        file_obj: BinaryIO,
        s3_key: str,
        content_type: str,
        filename: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Upload a file to S3.

        Args:
            file_obj: File-like object to upload
            s3_key: S3 object key
            content_type: MIME type of the file
            filename: Original filename for Content-Disposition

        Returns:
            Tuple of (success, error_message)
        """
        if not self.enabled:
            return False, "S3 service is not configured"

        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "ContentDisposition": f'attachment; filename="{filename}"',
                    "Metadata": {
                        "original_filename": filename,
                        "uploaded_at": datetime.utcnow().isoformat(),
                    },
                },
            )
            logger.info(f"Successfully uploaded file to S3: {s3_key}")
            return True, None
        except ClientError as e:
            error_msg = f"Failed to upload file to S3: {e}"
            logger.error(error_msg)
            return False, error_msg

    def generate_presigned_url(
        self,
        s3_key: str,
        expiration_seconds: int = 3600,
        for_download: bool = True,
    ) -> Optional[str]:
        """
        Generate a presigned URL for downloading or viewing a file.

        Args:
            s3_key: S3 object key
            expiration_seconds: URL expiration time in seconds (default 1 hour)
            for_download: If True, include Content-Disposition for download

        Returns:
            Presigned URL or None if error
        """
        if not self.enabled:
            return None

        try:
            params = {
                "Bucket": self.bucket_name,
                "Key": s3_key,
            }
            if for_download:
                # Let S3 use the stored Content-Disposition
                pass

            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiration_seconds,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None

    def generate_presigned_upload_url(
        self,
        s3_key: str,
        content_type: str,
        expiration_seconds: int = 3600,
    ) -> Optional[dict]:
        """
        Generate a presigned URL for direct browser upload.

        Args:
            s3_key: S3 object key
            content_type: Expected MIME type
            expiration_seconds: URL expiration time

        Returns:
            Dict with url and fields for form-based upload, or None
        """
        if not self.enabled:
            return None

        try:
            response = self.s3_client.generate_presigned_post(
                self.bucket_name,
                s3_key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, self.max_file_size_bytes],
                ],
                ExpiresIn=expiration_seconds,
            )
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned upload URL: {e}")
            return None

    def delete_file(self, s3_key: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a file from S3.

        Args:
            s3_key: S3 object key to delete

        Returns:
            Tuple of (success, error_message)
        """
        if not self.enabled:
            return False, "S3 service is not configured"

        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            logger.info(f"Successfully deleted file from S3: {s3_key}")
            return True, None
        except ClientError as e:
            error_msg = f"Failed to delete file from S3: {e}"
            logger.error(error_msg)
            return False, error_msg

    def get_file_info(self, s3_key: str) -> Optional[dict]:
        """
        Get metadata about a file in S3.

        Args:
            s3_key: S3 object key

        Returns:
            Dict with file info or None
        """
        if not self.enabled:
            return None

        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return {
                "content_type": response.get("ContentType"),
                "content_length": response.get("ContentLength"),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            logger.error(f"Failed to get file info from S3: {e}")
            return None

    def copy_file(self, source_key: str, dest_key: str) -> Tuple[bool, Optional[str]]:
        """
        Copy a file within S3 (used for versioning).

        Args:
            source_key: Source S3 key
            dest_key: Destination S3 key

        Returns:
            Tuple of (success, error_message)
        """
        if not self.enabled:
            return False, "S3 service is not configured"

        try:
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={"Bucket": self.bucket_name, "Key": source_key},
                Key=dest_key,
            )
            logger.info(f"Successfully copied file in S3: {source_key} -> {dest_key}")
            return True, None
        except ClientError as e:
            error_msg = f"Failed to copy file in S3: {e}"
            logger.error(error_msg)
            return False, error_msg


# Singleton instance
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """Get or create the S3 service singleton."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
