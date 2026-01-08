import boto3
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import S3Config
from .models import UploadTask, UploadStatus, CostMetrics
from .utils import calculate_checksum

logger = logging.getLogger(__name__)


class S3Client:
    """
    Optimized S3 client for cost-effective video uploads
    Handles multipart uploads, storage class selection, and cost tracking
    """

    def __init__(self, config: S3Config):
        self.config = config
        self.cost_metrics = CostMetrics()

        # Configure boto3 with optimizations
        boto_config = Config(
            region_name=config.region,
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            max_pool_connections=50
        )

        # Initialize S3 client
        self.client = boto3.client('s3', config=boto_config)

        # Multipart thresholds
        self.multipart_threshold = config.multipart_threshold_mb * 1024 * 1024
        self.multipart_chunksize = config.multipart_chunksize_mb * 1024 * 1024

    def upload_file(self, file_path: str, s3_key: str,
                   progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        """
        Upload file to S3 with automatic multipart handling

        Args:
            file_path: Local file path
            s3_key: S3 object key
            progress_callback: Optional callback for progress updates (receives bytes uploaded)

        Returns:
            True if upload successful
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return False

        file_size = path.stat().st_size

        try:
            # Determine if we should use multipart upload
            use_multipart = file_size >= self.multipart_threshold

            if use_multipart:
                logger.info(f"Using multipart upload for {file_path} ({file_size / (1024**2):.2f} MB)")
                success = self._multipart_upload(file_path, s3_key, progress_callback)
            else:
                logger.info(f"Using standard upload for {file_path} ({file_size / (1024**2):.2f} MB)")
                success = self._standard_upload(file_path, s3_key, progress_callback)

            if success:
                # Update cost metrics
                self.cost_metrics.total_bytes_uploaded += file_size
                self.cost_metrics.storage_bytes += file_size
                self.cost_metrics.total_requests += 1
                if use_multipart:
                    self.cost_metrics.multipart_requests += 1
                else:
                    self.cost_metrics.put_requests += 1

                logger.info(f"Successfully uploaded {file_path} to s3://{self.config.bucket_name}/{s3_key}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Upload failed for {file_path}: {e}")
            return False

    def _standard_upload(self, file_path: str, s3_key: str,
                        progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        """
        Standard single PUT upload for files < multipart threshold

        Args:
            file_path: Local file path
            s3_key: S3 object key
            progress_callback: Optional callback for progress

        Returns:
            True if successful
        """
        try:
            extra_args = {
                'StorageClass': self.config.storage_class
            }

            # Calculate checksum for integrity verification
            checksum = calculate_checksum(file_path)
            extra_args['Metadata'] = {'checksum-sha256': checksum}

            # Use transfer config for progress tracking
            if progress_callback:
                def upload_progress(bytes_amount):
                    progress_callback(bytes_amount)

                self.client.upload_file(
                    file_path,
                    self.config.bucket_name,
                    s3_key,
                    ExtraArgs=extra_args,
                    Callback=upload_progress
                )
            else:
                self.client.upload_file(
                    file_path,
                    self.config.bucket_name,
                    s3_key,
                    ExtraArgs=extra_args
                )

            return True

        except ClientError as e:
            logger.error(f"S3 ClientError during standard upload: {e}")
            return False

    def _multipart_upload(self, file_path: str, s3_key: str,
                         progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        """
        Multipart upload for large files

        Args:
            file_path: Local file path
            s3_key: S3 object key
            progress_callback: Optional callback for progress

        Returns:
            True if successful
        """
        try:
            # Calculate checksum
            checksum = calculate_checksum(file_path)

            # Initiate multipart upload
            response = self.client.create_multipart_upload(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                StorageClass=self.config.storage_class,
                Metadata={'checksum-sha256': checksum}
            )

            upload_id = response['UploadId']
            logger.info(f"Started multipart upload: {upload_id}")

            # Upload parts
            parts = []
            part_number = 1
            bytes_uploaded = 0

            with open(file_path, 'rb') as f:
                while True:
                    # Read chunk
                    data = f.read(self.multipart_chunksize)
                    if not data:
                        break

                    # Upload part
                    response = self.client.upload_part(
                        Bucket=self.config.bucket_name,
                        Key=s3_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=data
                    )

                    parts.append({
                        'PartNumber': part_number,
                        'ETag': response['ETag']
                    })

                    bytes_uploaded += len(data)
                    if progress_callback:
                        progress_callback(bytes_uploaded)

                    logger.debug(f"Uploaded part {part_number}")
                    part_number += 1

            # Complete multipart upload
            self.client.complete_multipart_upload(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )

            logger.info(f"Completed multipart upload: {upload_id}")
            return True

        except ClientError as e:
            logger.error(f"S3 ClientError during multipart upload: {e}")
            # Abort multipart upload on failure
            try:
                if 'upload_id' in locals():
                    self.client.abort_multipart_upload(
                        Bucket=self.config.bucket_name,
                        Key=s3_key,
                        UploadId=upload_id
                    )
                    logger.info(f"Aborted multipart upload: {upload_id}")
            except Exception as abort_error:
                logger.error(f"Failed to abort multipart upload: {abort_error}")
            return False

    def delete_file(self, s3_key: str) -> bool:
        """
        Delete file from S3

        Args:
            s3_key: S3 object key

        Returns:
            True if successful
        """
        try:
            self.client.delete_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )
            logger.info(f"Deleted s3://{self.config.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {s3_key}: {e}")
            return False

    def file_exists(self, s3_key: str) -> bool:
        """
        Check if file exists in S3

        Args:
            s3_key: S3 object key

        Returns:
            True if file exists
        """
        try:
            self.client.head_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"Error checking file existence: {e}")
                return False

    def get_file_metadata(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for S3 object

        Args:
            s3_key: S3 object key

        Returns:
            Dictionary with metadata, or None if not found
        """
        try:
            response = self.client.head_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )

            return {
                'size': response['ContentLength'],
                'last_modified': response['LastModified'],
                'etag': response['ETag'],
                'storage_class': response.get('StorageClass', 'STANDARD'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            logger.error(f"Failed to get metadata for {s3_key}: {e}")
            return None

    def list_files(self, prefix: str = "", max_keys: int = 1000) -> list:
        """
        List files in S3 bucket with given prefix

        Args:
            prefix: Key prefix to filter
            max_keys: Maximum number of keys to return

        Returns:
            List of S3 object summaries
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.config.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )

            return response.get('Contents', [])
        except ClientError as e:
            logger.error(f"Failed to list files: {e}")
            return []

    def get_cost_metrics(self) -> CostMetrics:
        """
        Get current cost metrics

        Returns:
            CostMetrics object
        """
        return self.cost_metrics

    def reset_cost_metrics(self):
        """Reset cost tracking metrics"""
        self.cost_metrics = CostMetrics()

    def set_bucket_lifecycle(self, transition_days: int = 30,
                           transition_class: str = "STANDARD_IA") -> bool:
        """
        Configure lifecycle policy to transition old objects to cheaper storage

        Args:
            transition_days: Days before transitioning
            transition_class: Target storage class

        Returns:
            True if successful
        """
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'Id': 'TransitionOldVideos',
                        'Status': 'Enabled',
                        'Prefix': self.config.key_prefix,
                        'Transitions': [
                            {
                                'Days': transition_days,
                                'StorageClass': transition_class
                            }
                        ]
                    }
                ]
            }

            self.client.put_bucket_lifecycle_configuration(
                Bucket=self.config.bucket_name,
                LifecycleConfiguration=lifecycle_config
            )

            logger.info(f"Set lifecycle policy: transition to {transition_class} after {transition_days} days")
            return True

        except ClientError as e:
            logger.error(f"Failed to set lifecycle policy: {e}")
            return False

    def verify_upload(self, file_path: str, s3_key: str) -> bool:
        """
        Verify uploaded file matches local file

        Args:
            file_path: Local file path
            s3_key: S3 object key

        Returns:
            True if checksums match
        """
        try:
            # Get local checksum
            local_checksum = calculate_checksum(file_path)

            # Get S3 metadata
            metadata = self.get_file_metadata(s3_key)
            if not metadata:
                return False

            # Compare checksums
            s3_checksum = metadata.get('metadata', {}).get('checksum-sha256', '')

            if local_checksum == s3_checksum:
                logger.info(f"Upload verification successful for {s3_key}")
                return True
            else:
                logger.error(f"Upload verification failed: checksum mismatch for {s3_key}")
                return False

        except Exception as e:
            logger.error(f"Upload verification error: {e}")
            return False
