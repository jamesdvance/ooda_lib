import subprocess
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from .models import VideoRecord, VideoStatus, BatchRecord, VideoMetadata
from .config import CompressionConfig, BatchConfig
from .utils import get_video_metadata, ensure_dir_exists

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Handles video compression and batching operations
    """

    def __init__(self, compression_config: CompressionConfig, batch_config: BatchConfig,
                 processed_dir: str, batches_dir: str):
        self.compression_config = compression_config
        self.batch_config = batch_config
        self.processed_dir = Path(processed_dir)
        self.batches_dir = Path(batches_dir)

        # Ensure directories exist
        ensure_dir_exists(self.processed_dir)
        ensure_dir_exists(self.batches_dir)

    def compress_video(self, input_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Compress video using ffmpeg with H.265 codec

        Args:
            input_path: Path to input video
            output_path: Optional output path (auto-generated if not provided)

        Returns:
            Path to compressed video, or None if compression failed
        """
        if not self.compression_config.enabled:
            return input_path

        # Check if ffmpeg is available
        if not shutil.which('ffmpeg'):
            logger.warning("ffmpeg not found, skipping compression")
            return input_path

        # Generate output path if not provided
        if output_path is None:
            input_file = Path(input_path)
            output_path = str(self.processed_dir / f"{input_file.stem}_compressed{input_file.suffix}")

        try:
            # Build ffmpeg command
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', self.compression_config.codec,
                '-crf', str(self.compression_config.crf),
                '-preset', self.compression_config.preset,
                '-c:a', self.compression_config.audio_codec,
                '-b:a', self.compression_config.audio_bitrate,
            ]

            # Add resolution scaling if specified
            if self.compression_config.max_resolution:
                cmd.extend(['-vf', f'scale={self.compression_config.max_resolution}'])

            # Add output file and overwrite flag
            cmd.extend(['-y', output_path])

            # Run ffmpeg
            logger.info(f"Compressing video: {input_path} -> {output_path}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode == 0:
                # Verify output file exists
                if Path(output_path).exists():
                    original_size = Path(input_path).stat().st_size
                    compressed_size = Path(output_path).stat().st_size
                    reduction = ((original_size - compressed_size) / original_size) * 100

                    logger.info(f"Compression successful: {reduction:.1f}% size reduction")
                    return output_path
                else:
                    logger.error(f"Compression failed: output file not created")
                    return None
            else:
                logger.error(f"ffmpeg failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("Compression timeout (>1 hour)")
            return None
        except Exception as e:
            logger.error(f"Compression error: {e}")
            return None

    def create_batch(self, videos: List[VideoRecord]) -> Optional[BatchRecord]:
        """
        Combine multiple videos into a single batch file

        Args:
            videos: List of video records to batch

        Returns:
            BatchRecord if successful, None otherwise
        """
        if not self.batch_config.enabled or len(videos) < self.batch_config.min_files:
            return None

        # Check if ffmpeg is available
        if not shutil.which('ffmpeg'):
            logger.warning("ffmpeg not found, skipping batching")
            return None

        try:
            # Generate batch ID and output path
            batch_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = self.batches_dir / f"batch_{timestamp}_{batch_id}.mp4"

            # Create concat file for ffmpeg
            concat_file = self.batches_dir / f"concat_{batch_id}.txt"

            # Sort videos by timestamp
            sorted_videos = sorted(videos, key=lambda v: v.created_at)

            # Write concat file
            with open(concat_file, 'w') as f:
                for video in sorted_videos:
                    # Use processed path if available, otherwise original
                    video_path = video.processed_path or video.original_path
                    # Escape single quotes in path
                    escaped_path = video_path.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")

            # Build ffmpeg command for concatenation
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',  # Copy streams without re-encoding
                '-y',
                str(output_path)
            ]

            logger.info(f"Creating batch of {len(videos)} videos")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            # Clean up concat file
            concat_file.unlink()

            if result.returncode == 0 and output_path.exists():
                # Calculate batch metadata
                total_size = output_path.stat().st_size
                start_time = sorted_videos[0].created_at
                end_time = sorted_videos[-1].created_at

                batch = BatchRecord(
                    id=batch_id,
                    video_ids=[v.id for v in sorted_videos],
                    batch_path=str(output_path),
                    start_time=start_time,
                    end_time=end_time,
                    total_size=total_size,
                    video_count=len(videos),
                    status=VideoStatus.READY
                )

                logger.info(f"Batch created: {batch}")
                return batch
            else:
                logger.error(f"Batch creation failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Batch creation error: {e}")
            return None

    def group_videos_for_batching(self, videos: List[VideoRecord]) -> List[List[VideoRecord]]:
        """
        Group videos into batches based on time windows

        Args:
            videos: List of video records to group

        Returns:
            List of video groups (each group is a list of videos)
        """
        if not videos or not self.batch_config.enabled:
            return []

        # Sort videos by creation time
        sorted_videos = sorted(videos, key=lambda v: v.created_at)

        groups = []
        current_group = []
        current_size = 0
        window_start = None

        max_batch_size = self.batch_config.max_batch_size_mb * 1024 * 1024
        window_duration = timedelta(hours=self.batch_config.window_hours)

        for video in sorted_videos:
            # Get video size
            video_path = video.processed_path or video.original_path
            try:
                video_size = Path(video_path).stat().st_size
            except Exception:
                continue

            # Initialize window if this is the first video
            if window_start is None:
                window_start = video.created_at

            # Check if video fits in current window and size limit
            in_window = (video.created_at - window_start) <= window_duration
            size_ok = (current_size + video_size) <= max_batch_size

            if in_window and size_ok:
                # Add to current group
                current_group.append(video)
                current_size += video_size
            else:
                # Start new group
                if current_group and len(current_group) >= self.batch_config.min_files:
                    groups.append(current_group)

                current_group = [video]
                current_size = video_size
                window_start = video.created_at

        # Add final group if it meets minimum size
        if current_group and len(current_group) >= self.batch_config.min_files:
            groups.append(current_group)

        logger.info(f"Grouped {len(videos)} videos into {len(groups)} batches")
        return groups

    def process_video(self, video: VideoRecord) -> bool:
        """
        Process a single video (compress if enabled)

        Args:
            video: VideoRecord to process

        Returns:
            True if processing successful
        """
        try:
            logger.info(f"Processing video: {video.id}")

            # Mark as processing
            video.mark_processing()

            if self.compression_config.enabled:
                # Compress video
                compressed_path = self.compress_video(video.original_path)

                if compressed_path:
                    video.mark_ready(compressed_path)
                    logger.info(f"Video processed successfully: {video.id}")
                    return True
                else:
                    video.mark_failed("Compression failed")
                    logger.error(f"Failed to process video: {video.id}")
                    return False
            else:
                # No compression, just mark as ready
                video.mark_ready(video.original_path)
                logger.info(f"Video marked ready (no compression): {video.id}")
                return True

        except Exception as e:
            video.mark_failed(f"Processing error: {e}")
            logger.error(f"Error processing video {video.id}: {e}")
            return False

    def get_compression_estimate(self, input_path: str) -> dict:
        """
        Estimate compression results without actually compressing

        Args:
            input_path: Path to input video

        Returns:
            Dictionary with size estimates
        """
        metadata = get_video_metadata(input_path)

        # Rough estimate: H.265 at CRF 28 typically achieves 40-60% size reduction
        # This varies based on content, but provides a ballpark estimate
        estimated_reduction = 0.5  # 50% reduction
        estimated_size = metadata.file_size * (1 - estimated_reduction)

        return {
            'original_size_mb': metadata.file_size_mb,
            'estimated_size_mb': estimated_size / (1024 * 1024),
            'estimated_reduction_percent': estimated_reduction * 100,
            'duration_seconds': metadata.duration,
            'codec': metadata.codec
        }
