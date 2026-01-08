"""
OODA Upload Module

Cost-effective video upload system for S3 with:
- H.265 compression for 40-60% size reduction
- Intelligent batching by time window
- Scheduled uploads to minimize request costs
- Multipart upload for large files
- Crash recovery with SQLite persistence
- Network-aware scheduling
- Cost tracking and optimization

Example usage:

    from ooda.upload import Upload, UploadConfig

    # Simple usage with defaults
    uploader = Upload()
    uploader.add_video('/path/to/video.mp4')
    uploader.run_upload_cycle()

    # Automatic scheduled uploads
    uploader = Upload()
    uploader.start_automatic_uploads()

    # Custom configuration
    config = UploadConfig.load('config.yaml')
    uploader = Upload(config=config)

    # Context manager
    with Upload() as uploader:
        uploader.add_video('/path/to/video.mp4')
        uploader.run_upload_cycle()
"""

from .upload import Upload
from .config import (
    UploadConfig,
    CompressionConfig,
    BatchConfig,
    ScheduleConfig,
    StorageConfig,
    S3Config,
    MonitoringConfig
)
from .models import (
    VideoRecord,
    VideoStatus,
    VideoMetadata,
    BatchRecord,
    UploadTask,
    UploadStatus,
    CostMetrics
)
from .storage import StorageManager
from .processor import VideoProcessor
from .s3_client import S3Client
from .scheduler import UploadScheduler

__all__ = [
    # Main class
    'Upload',

    # Configuration
    'UploadConfig',
    'CompressionConfig',
    'BatchConfig',
    'ScheduleConfig',
    'StorageConfig',
    'S3Config',
    'MonitoringConfig',

    # Models
    'VideoRecord',
    'VideoStatus',
    'VideoMetadata',
    'BatchRecord',
    'UploadTask',
    'UploadStatus',
    'CostMetrics',

    # Components (for advanced usage)
    'StorageManager',
    'VideoProcessor',
    'S3Client',
    'UploadScheduler',
]

__version__ = '1.0.0'
