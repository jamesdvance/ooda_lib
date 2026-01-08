from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List


class VideoStatus(Enum):
    """Status of video in the upload pipeline"""
    PENDING = "pending"  # Waiting to be processed
    PROCESSING = "processing"  # Being compressed/batched
    READY = "ready"  # Ready for upload
    UPLOADING = "uploading"  # Currently uploading
    UPLOADED = "uploaded"  # Successfully uploaded
    FAILED = "failed"  # Upload failed
    ARCHIVED = "archived"  # Uploaded and local file deleted


class UploadStatus(Enum):
    """Status of an upload operation"""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class VideoMetadata:
    """Metadata for a video file"""
    file_path: str
    file_size: int  # bytes
    checksum: str  # SHA-256 hash
    created_at: datetime
    duration: Optional[float] = None  # seconds
    width: Optional[int] = None
    height: Optional[int] = None
    codec: Optional[str] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return self.file_size / (1024 * 1024)

    def __str__(self) -> str:
        return f"VideoMetadata(path={self.file_path}, size={self.file_size_mb:.2f}MB, checksum={self.checksum[:8]}...)"


@dataclass
class VideoRecord:
    """Record of a video in the upload queue"""
    id: str  # Unique identifier (UUID)
    original_path: str
    processed_path: Optional[str] = None  # Path after compression
    metadata: Optional[VideoMetadata] = None
    status: VideoStatus = VideoStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    upload_attempts: int = 0
    last_error: Optional[str] = None
    s3_key: Optional[str] = None  # S3 key after upload
    batch_id: Optional[str] = None  # ID of batch this video belongs to

    def mark_processing(self):
        """Mark video as being processed"""
        self.status = VideoStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def mark_ready(self, processed_path: str):
        """Mark video as ready for upload"""
        self.status = VideoStatus.READY
        self.processed_path = processed_path
        self.updated_at = datetime.utcnow()

    def mark_uploading(self):
        """Mark video as currently uploading"""
        self.status = VideoStatus.UPLOADING
        self.upload_attempts += 1
        self.updated_at = datetime.utcnow()

    def mark_uploaded(self, s3_key: str):
        """Mark video as successfully uploaded"""
        self.status = VideoStatus.UPLOADED
        self.s3_key = s3_key
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error: str):
        """Mark video upload as failed"""
        self.status = VideoStatus.FAILED
        self.last_error = error
        self.updated_at = datetime.utcnow()

    def mark_archived(self):
        """Mark video as archived (uploaded and deleted locally)"""
        self.status = VideoStatus.ARCHIVED
        self.updated_at = datetime.utcnow()


@dataclass
class BatchRecord:
    """Record of a batch of videos combined together"""
    id: str  # Unique identifier (UUID)
    video_ids: List[str]  # IDs of videos in this batch
    batch_path: str  # Path to the combined video file
    start_time: datetime
    end_time: datetime
    total_size: int  # bytes
    video_count: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: VideoStatus = VideoStatus.READY
    s3_key: Optional[str] = None

    @property
    def total_size_mb(self) -> float:
        """Get total size in MB"""
        return self.total_size / (1024 * 1024)

    @property
    def duration_hours(self) -> float:
        """Get batch duration in hours"""
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600

    def __str__(self) -> str:
        return f"BatchRecord(id={self.id}, videos={self.video_count}, size={self.total_size_mb:.2f}MB, duration={self.duration_hours:.2f}h)"


@dataclass
class UploadTask:
    """Task representing an upload operation"""
    id: str  # Unique identifier
    file_path: str
    s3_key: str
    file_size: int  # bytes
    checksum: str
    status: UploadStatus = UploadStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempts: int = 0
    last_error: Optional[str] = None
    bytes_uploaded: int = 0
    use_multipart: bool = False
    upload_id: Optional[str] = None  # S3 multipart upload ID

    @property
    def progress_percent(self) -> float:
        """Get upload progress percentage"""
        if self.file_size == 0:
            return 0.0
        return (self.bytes_uploaded / self.file_size) * 100

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get upload duration in seconds"""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    @property
    def upload_speed_mbps(self) -> Optional[float]:
        """Get upload speed in Mbps"""
        duration = self.duration_seconds
        if duration is None or duration == 0:
            return None
        bytes_per_second = self.bytes_uploaded / duration
        return (bytes_per_second * 8) / (1024 * 1024)

    def mark_started(self):
        """Mark upload as started"""
        self.status = UploadStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.attempts += 1

    def mark_completed(self):
        """Mark upload as completed"""
        self.status = UploadStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.bytes_uploaded = self.file_size

    def mark_failed(self, error: str):
        """Mark upload as failed"""
        self.status = UploadStatus.FAILED
        self.last_error = error

    def mark_retrying(self):
        """Mark upload as retrying"""
        self.status = UploadStatus.RETRYING


@dataclass
class CostMetrics:
    """Track cost-related metrics"""
    total_bytes_uploaded: int = 0
    total_requests: int = 0
    put_requests: int = 0
    multipart_requests: int = 0
    storage_bytes: int = 0
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: Optional[datetime] = None

    @property
    def total_gb_uploaded(self) -> float:
        """Get total GB uploaded"""
        return self.total_bytes_uploaded / (1024 * 1024 * 1024)

    @property
    def total_gb_stored(self) -> float:
        """Get total GB stored"""
        return self.storage_bytes / (1024 * 1024 * 1024)

    def estimate_cost_usd(self, region: str = "us-east-1") -> dict:
        """
        Estimate monthly costs in USD
        Based on AWS S3 pricing (approximate, may vary by region)
        """
        # Approximate pricing for us-east-1 (as of 2024)
        storage_cost_per_gb = 0.023  # Standard storage
        put_cost_per_1000 = 0.005
        data_transfer_out_per_gb = 0.09  # First 10TB

        storage_cost = self.total_gb_stored * storage_cost_per_gb
        request_cost = (self.put_requests / 1000) * put_cost_per_1000
        # Note: No data transfer cost for uploads TO S3

        return {
            "storage_usd": round(storage_cost, 4),
            "requests_usd": round(request_cost, 4),
            "total_usd": round(storage_cost + request_cost, 4),
            "total_gb_uploaded": round(self.total_gb_uploaded, 2),
            "total_gb_stored": round(self.total_gb_stored, 2),
            "total_requests": self.total_requests
        }

    def __str__(self) -> str:
        costs = self.estimate_cost_usd()
        return f"CostMetrics(uploaded={costs['total_gb_uploaded']}GB, stored={costs['total_gb_stored']}GB, cost=${costs['total_usd']})"
