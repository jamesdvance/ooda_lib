import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .config import UploadConfig
from .storage import StorageManager
from .processor import VideoProcessor
from .s3_client import S3Client
from .scheduler import UploadScheduler
from .models import VideoStatus, VideoRecord
from .utils import get_video_metadata, generate_s3_key, is_video_file

logger = logging.getLogger(__name__)


class Upload:
    """
    Main upload manager class that orchestrates cost-effective video uploads to S3

    Features:
    - Automatic video compression with H.265 codec
    - Intelligent batching of videos by time window
    - Scheduled uploads to minimize request costs
    - Multipart upload for large files
    - Crash recovery with SQLite persistence
    - Network awareness
    - Cost tracking and optimization
    """

    def __init__(self, config: Optional[UploadConfig] = None, config_path: Optional[str] = None):
        """
        Initialize upload manager

        Args:
            config: UploadConfig object (if not provided, will load from file/env)
            config_path: Path to config file (optional)
        """
        # Load configuration
        if config is None:
            self.config = UploadConfig.load(config_path)
        else:
            self.config = config

        # Setup logging
        self._setup_logging()

        # Initialize components
        self.storage = StorageManager(self.config.storage)
        self.processor = VideoProcessor(
            self.config.compression,
            self.config.batching,
            str(self.storage.processed_dir),
            str(self.storage.batches_dir)
        )
        self.s3_client = S3Client(self.config.s3)
        self.scheduler = UploadScheduler(self.config.schedule)

        logger.info("Upload manager initialized")
        logger.info(f"Compression: {'enabled' if self.config.compression.enabled else 'disabled'}")
        logger.info(f"Batching: {'enabled' if self.config.batching.enabled else 'disabled'}")
        logger.info(f"Upload interval: {self.config.schedule.upload_interval_hours}h")

    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config.monitoring.log_level.upper())
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format=log_format
        )

        # Add file handler if log file is specified
        if self.config.monitoring.log_file:
            file_handler = logging.FileHandler(self.config.monitoring.log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(logging.Formatter(log_format))
            logging.getLogger().addHandler(file_handler)

    def add_video(self, file_path: str) -> Optional[str]:
        """
        Add a video to the upload queue

        Args:
            file_path: Path to video file

        Returns:
            Video ID if successful, None otherwise
        """
        path = Path(file_path)

        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        if not is_video_file(file_path):
            logger.warning(f"File may not be a video: {file_path}")

        try:
            # Get video metadata
            metadata = get_video_metadata(file_path)
            logger.info(f"Adding video: {file_path} ({metadata.file_size_mb:.2f} MB)")

            # Add to storage
            video = self.storage.add_video(file_path)

            # Check if storage is critical
            if self.storage.is_storage_critical():
                logger.warning("Storage critical! Forcing immediate upload")
                self.scheduler.force_upload_now()

            return video.id

        except Exception as e:
            logger.error(f"Failed to add video {file_path}: {e}")
            return None

    def process_pending_videos(self) -> int:
        """
        Process all pending videos (compress and/or batch)

        Returns:
            Number of videos processed
        """
        logger.info("Processing pending videos")

        # Get pending videos
        pending = self.storage.get_pending_videos()
        if not pending:
            logger.info("No pending videos to process")
            return 0

        logger.info(f"Found {len(pending)} pending videos")
        processed_count = 0

        # Process individual videos
        for video in pending:
            try:
                if self.processor.process_video(video):
                    self.storage.update_video(video)
                    processed_count += 1
                else:
                    logger.error(f"Failed to process video: {video.id}")
                    self.storage.update_video(video)
            except Exception as e:
                logger.error(f"Error processing video {video.id}: {e}")
                video.mark_failed(str(e))
                self.storage.update_video(video)

        logger.info(f"Processed {processed_count}/{len(pending)} videos")

        # Create batches if enabled
        if self.config.batching.enabled:
            self._create_batches()

        return processed_count

    def _create_batches(self) -> int:
        """
        Create batches from ready videos

        Returns:
            Number of batches created
        """
        logger.info("Creating batches from ready videos")

        # Get videos ready for batching (not already in a batch)
        ready_videos = [v for v in self.storage.get_ready_videos() if v.batch_id is None]

        if not ready_videos:
            logger.info("No videos available for batching")
            return 0

        # Group videos into batches
        groups = self.processor.group_videos_for_batching(ready_videos)

        if not groups:
            logger.info("No batches created (insufficient videos or within time window)")
            return 0

        batch_count = 0
        for group in groups:
            try:
                batch = self.processor.create_batch(group)
                if batch:
                    # Save batch
                    self.storage.add_batch(batch)

                    # Update videos with batch ID
                    for video in group:
                        video.batch_id = batch.id
                        self.storage.update_video(video)

                    batch_count += 1
                    logger.info(f"Created batch: {batch}")
            except Exception as e:
                logger.error(f"Failed to create batch: {e}")

        logger.info(f"Created {batch_count} batches")
        return batch_count

    def upload_all(self) -> bool:
        """
        Upload all ready videos and batches to S3

        Returns:
            True if all uploads successful
        """
        logger.info("Starting upload of all ready items")

        success = True

        # Upload batches first (if batching is enabled)
        if self.config.batching.enabled:
            batches = self.storage.get_ready_batches()
            logger.info(f"Uploading {len(batches)} batches")

            for batch in batches:
                if not self._upload_batch(batch):
                    success = False

        # Upload individual ready videos (not in batches)
        ready_videos = [v for v in self.storage.get_ready_videos() if v.batch_id is None]
        logger.info(f"Uploading {len(ready_videos)} individual videos")

        for video in ready_videos:
            if not self._upload_video(video):
                success = False

        # Cleanup uploaded files
        self.storage.cleanup_uploaded_files()

        # Mark upload complete in scheduler
        if success:
            self.scheduler.mark_upload_complete()

        return success

    def _upload_video(self, video: VideoRecord) -> bool:
        """
        Upload a single video to S3

        Args:
            video: VideoRecord to upload

        Returns:
            True if successful
        """
        try:
            # Mark as uploading
            video.mark_uploading()
            self.storage.update_video(video)

            # Determine file to upload (processed or original)
            upload_path = video.processed_path or video.original_path

            # Generate S3 key
            s3_key = generate_s3_key(upload_path, self.config.s3.key_prefix)

            # Upload to S3
            logger.info(f"Uploading video {video.id} to {s3_key}")

            def progress_callback(bytes_uploaded):
                logger.debug(f"Upload progress: {bytes_uploaded} bytes")

            success = self.s3_client.upload_file(upload_path, s3_key, progress_callback)

            if success:
                # Verify upload
                if self.s3_client.verify_upload(upload_path, s3_key):
                    video.mark_uploaded(s3_key)
                    self.storage.update_video(video)
                    logger.info(f"Successfully uploaded video {video.id}")
                    return True
                else:
                    video.mark_failed("Upload verification failed")
                    self.storage.update_video(video)
                    return False
            else:
                video.mark_failed("Upload failed")
                self.storage.update_video(video)
                return False

        except Exception as e:
            logger.error(f"Error uploading video {video.id}: {e}")
            video.mark_failed(str(e))
            self.storage.update_video(video)
            return False

    def _upload_batch(self, batch) -> bool:
        """
        Upload a batch to S3

        Args:
            batch: BatchRecord to upload

        Returns:
            True if successful
        """
        try:
            # Generate S3 key
            s3_key = generate_s3_key(batch.batch_path, f"{self.config.s3.key_prefix}/batches")

            # Upload to S3
            logger.info(f"Uploading batch {batch.id} to {s3_key}")

            success = self.s3_client.upload_file(batch.batch_path, s3_key)

            if success:
                batch.status = VideoStatus.UPLOADED
                batch.s3_key = s3_key
                self.storage.update_batch(batch)
                logger.info(f"Successfully uploaded batch {batch.id}")
                return True
            else:
                logger.error(f"Failed to upload batch {batch.id}")
                return False

        except Exception as e:
            logger.error(f"Error uploading batch {batch.id}: {e}")
            return False

    def run_upload_cycle(self) -> bool:
        """
        Run a complete upload cycle: process -> upload

        Returns:
            True if successful
        """
        logger.info("=== Starting upload cycle ===")

        try:
            # Process pending videos
            processed = self.process_pending_videos()
            logger.info(f"Processed {processed} videos")

            # Upload all ready items
            success = self.upload_all()

            logger.info("=== Upload cycle complete ===")
            return success

        except Exception as e:
            logger.error(f"Error in upload cycle: {e}")
            return False

    def start_automatic_uploads(self):
        """
        Start automatic scheduled uploads
        """
        logger.info("Starting automatic upload scheduler")

        def upload_callback():
            return self.run_upload_cycle()

        self.scheduler.start_scheduled_uploads(upload_callback)

    def stop_automatic_uploads(self):
        """
        Stop automatic scheduled uploads
        """
        logger.info("Stopping automatic upload scheduler")
        self.scheduler.stop_scheduled_uploads()

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of upload system

        Returns:
            Dictionary with status information
        """
        stats = self.storage.get_statistics()
        scheduler_status = self.scheduler.get_status()
        cost_metrics = self.s3_client.get_cost_metrics()

        return {
            'storage': stats,
            'scheduler': scheduler_status,
            'costs': cost_metrics.estimate_cost_usd(),
            'config': {
                'compression_enabled': self.config.compression.enabled,
                'batching_enabled': self.config.batching.enabled,
                'upload_interval_hours': self.config.schedule.upload_interval_hours,
                'batch_window_hours': self.config.batching.window_hours,
                'buffer_dir': self.config.storage.buffer_dir,
                's3_bucket': self.config.s3.bucket_name,
                's3_storage_class': self.config.s3.storage_class
            }
        }

    def cleanup(self):
        """
        Cleanup old and failed files
        """
        logger.info("Running cleanup")
        self.storage.cleanup_uploaded_files()
        self.storage.cleanup_failed_files()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_automatic_uploads()
