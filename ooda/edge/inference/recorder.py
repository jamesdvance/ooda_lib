"""
Video recording module for continuous video capture with segmentation.
"""
import cv2
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger
from config import VideoConfig, StorageConfig


class VideoRecorder:
    """Handles video capture and recording with automatic segmentation."""

    def __init__(self, video_config: VideoConfig, storage_config: StorageConfig):
        self.video_config = video_config
        self.storage_config = storage_config
        self.capture: Optional[cv2.VideoCapture] = None
        self.writer: Optional[cv2.VideoWriter] = None
        self.current_segment_path: Optional[Path] = None
        self.segment_start_time: Optional[float] = None
        self.frame_count = 0

        # Ensure directories exist
        self.storage_config.recording_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> bool:
        """Initialize video capture."""
        logger.info(f"Starting video capture from source: {self.video_config.source}")

        # Initialize video capture
        source = self.video_config.source
        if isinstance(source, str) and source.isdigit():
            source = int(source)

        self.capture = cv2.VideoCapture(source)

        if not self.capture.isOpened():
            logger.error(f"Failed to open video source: {source}")
            return False

        # Set capture properties
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.video_config.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.video_config.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.video_config.fps)

        # Get actual properties (might differ from requested)
        actual_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.capture.get(cv2.CAP_PROP_FPS))

        logger.info(
            f"Video capture initialized: {actual_width}x{actual_height} @ {actual_fps}fps"
        )

        return True

    def _create_new_segment(self) -> bool:
        """Create a new video segment file."""
        # Close previous writer if exists
        if self.writer is not None:
            self.writer.release()
            if self.current_segment_path:
                logger.info(f"Closed segment: {self.current_segment_path.name}")

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}.mp4"
        self.current_segment_path = self.storage_config.recording_dir / filename

        # Get video properties
        width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.video_config.fps

        # Create video writer with H.264 codec
        fourcc = cv2.VideoWriter_fourcc(*self.video_config.codec)
        self.writer = cv2.VideoWriter(
            str(self.current_segment_path), fourcc, fps, (width, height)
        )

        if not self.writer.isOpened():
            logger.error(f"Failed to create video writer for {self.current_segment_path}")
            return False

        self.segment_start_time = time.time()
        logger.info(f"Started new segment: {filename}")
        return True

    def read_frame(self) -> Tuple[bool, Optional[cv2.Mat]]:
        """
        Read a frame from the video source and write to current segment.

        Returns:
            Tuple of (success, frame)
        """
        if self.capture is None:
            return False, None

        ret, frame = self.capture.read()
        if not ret:
            logger.warning("Failed to read frame from video source")
            return False, None

        # Check if we need to create a new segment
        if self.writer is None or self._should_create_new_segment():
            if not self._create_new_segment():
                return False, None

        # Write frame to current segment
        self.writer.write(frame)
        self.frame_count += 1

        return True, frame

    def _should_create_new_segment(self) -> bool:
        """Check if it's time to create a new segment."""
        if self.segment_start_time is None:
            return True

        elapsed = time.time() - self.segment_start_time
        return elapsed >= self.video_config.segment_duration

    def get_current_segment_path(self) -> Optional[Path]:
        """Get the path to the current segment being recorded."""
        return self.current_segment_path

    def get_frame_count(self) -> int:
        """Get the total number of frames recorded."""
        return self.frame_count

    def stop(self):
        """Stop video capture and recording."""
        logger.info("Stopping video recorder")

        if self.writer is not None:
            self.writer.release()
            logger.info(f"Released video writer for {self.current_segment_path}")

        if self.capture is not None:
            self.capture.release()
            logger.info("Released video capture")

        self.writer = None
        self.capture = None

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
