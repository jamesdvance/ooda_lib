"""
Configuration management for the inference pipeline.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VideoConfig:
    """Video capture and recording configuration."""
    # Video source (0 for default camera, or path to video file, or RTSP URL)
    source: str = "0"

    # Resolution
    width: int = 1920
    height: int = 1080

    # Frame rate
    fps: int = 30

    # Codec for video encoding (use 'avc1' for H.264, 'mp4v' for MPEG-4)
    codec: str = "avc1"

    # Recording segment duration in seconds (create new file every N seconds)
    segment_duration: int = 300  # 5 minutes

    # Buffer size for video writer
    buffer_size: int = 10


@dataclass
class InferenceConfig:
    """Inference configuration for license plate recognition."""
    # Enable/disable inference
    enabled: bool = True

    # Inference frequency (process every Nth frame)
    frame_interval: int = 30  # Process 1 frame per second at 30fps

    # Batch size for inference
    batch_size: int = 4

    # Confidence threshold for detections
    confidence_threshold: float = 0.5

    # Maximum number of plates to detect per frame
    max_detections: int = 10


@dataclass
class StorageConfig:
    """Storage configuration for video files and metadata."""
    # Base directory for recordings
    recording_dir: Path = Path("/data/recordings")

    # Buffer directory (for files ready to upload)
    buffer_dir: Path = Path("/data/video_buffer")

    # Maximum storage size in GB
    max_storage_gb: float = 50.0

    # Minimum free space to maintain in GB
    min_free_space_gb: float = 5.0

    # Delete old files when storage is full
    auto_cleanup: bool = True

    # Store inference results as JSON
    save_inference_results: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    log_file: Path = Path("/var/log/ooda/inference.log")
    log_level: str = "INFO"
    log_rotation: str = "100 MB"
    log_retention: str = "7 days"


@dataclass
class Config:
    """Main configuration container."""
    video: VideoConfig
    inference: InferenceConfig
    storage: StorageConfig
    logging: LoggingConfig

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        video_source = os.getenv("OODA_VIDEO_SOURCE", "0")
        if video_source.isdigit():
            video_source = int(video_source)

        video = VideoConfig(
            source=video_source,
            width=int(os.getenv("OODA_VIDEO_WIDTH", "1920")),
            height=int(os.getenv("OODA_VIDEO_HEIGHT", "1080")),
            fps=int(os.getenv("OODA_VIDEO_FPS", "30")),
            codec=os.getenv("OODA_VIDEO_CODEC", "avc1"),
            segment_duration=int(os.getenv("OODA_SEGMENT_DURATION", "300")),
        )

        inference = InferenceConfig(
            enabled=os.getenv("OODA_INFERENCE_ENABLED", "true").lower() == "true",
            frame_interval=int(os.getenv("OODA_FRAME_INTERVAL", "30")),
            batch_size=int(os.getenv("OODA_BATCH_SIZE", "4")),
            confidence_threshold=float(os.getenv("OODA_CONFIDENCE_THRESHOLD", "0.5")),
        )

        storage = StorageConfig(
            recording_dir=Path(os.getenv("OODA_RECORDING_DIR", "/data/recordings")),
            buffer_dir=Path(os.getenv("OODA_BUFFER_DIR", "/data/video_buffer")),
            max_storage_gb=float(os.getenv("OODA_MAX_STORAGE_GB", "50.0")),
            min_free_space_gb=float(os.getenv("OODA_MIN_FREE_SPACE_GB", "5.0")),
            auto_cleanup=os.getenv("OODA_AUTO_CLEANUP", "true").lower() == "true",
            save_inference_results=os.getenv("OODA_SAVE_INFERENCE", "true").lower() == "true",
        )

        logging = LoggingConfig(
            log_file=Path(os.getenv("OODA_LOG_FILE", "/var/log/ooda/inference.log")),
            log_level=os.getenv("OODA_LOG_LEVEL", "INFO"),
        )

        return cls(
            video=video,
            inference=inference,
            storage=storage,
            logging=logging,
        )
