"""
Storage management for video files and cleanup operations.
"""
import shutil
from pathlib import Path
from typing import List, Tuple
from datetime import datetime
from loguru import logger

from config import StorageConfig


class StorageManager:
    """Manages storage of video files and performs cleanup operations."""

    def __init__(self, storage_config: StorageConfig):
        self.config = storage_config

        # Ensure directories exist
        self.config.recording_dir.mkdir(parents=True, exist_ok=True)
        self.config.buffer_dir.mkdir(parents=True, exist_ok=True)

    def get_disk_usage(self) -> Tuple[float, float, float]:
        """
        Get disk usage statistics.

        Returns:
            Tuple of (total_gb, used_gb, free_gb)
        """
        stat = shutil.disk_usage(self.config.recording_dir)
        total_gb = stat.total / (1024**3)
        used_gb = stat.used / (1024**3)
        free_gb = stat.free / (1024**3)
        return total_gb, used_gb, free_gb

    def get_directory_size(self, directory: Path) -> float:
        """
        Calculate total size of a directory in GB.

        Args:
            directory: Path to directory

        Returns:
            Size in GB
        """
        total_size = 0
        for item in directory.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
        return total_size / (1024**3)

    def get_video_files(self, directory: Path) -> List[Tuple[Path, datetime]]:
        """
        Get list of video files sorted by modification time (oldest first).

        Args:
            directory: Path to directory

        Returns:
            List of (file_path, modification_time) tuples
        """
        video_extensions = {".mp4", ".avi", ".mov", ".mkv"}
        files = []

        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                files.append((file_path, mod_time))

        # Sort by modification time (oldest first)
        files.sort(key=lambda x: x[1])
        return files

    def check_storage_limits(self) -> bool:
        """
        Check if storage limits are exceeded.

        Returns:
            True if storage is within limits, False otherwise
        """
        total_gb, used_gb, free_gb = self.get_disk_usage()
        recording_size = self.get_directory_size(self.config.recording_dir)

        logger.debug(
            f"Storage: {used_gb:.2f}/{total_gb:.2f} GB used, "
            f"{free_gb:.2f} GB free, "
            f"recordings: {recording_size:.2f} GB"
        )

        # Check free space
        if free_gb < self.config.min_free_space_gb:
            logger.warning(
                f"Low disk space: {free_gb:.2f} GB free "
                f"(minimum: {self.config.min_free_space_gb} GB)"
            )
            return False

        # Check recording directory size
        if recording_size > self.config.max_storage_gb:
            logger.warning(
                f"Recording directory exceeds limit: {recording_size:.2f} GB "
                f"(maximum: {self.config.max_storage_gb} GB)"
            )
            return False

        return True

    def cleanup_old_files(self, target_free_gb: float = None) -> int:
        """
        Delete oldest files until storage limits are met.

        Args:
            target_free_gb: Target free space in GB (uses config if None)

        Returns:
            Number of files deleted
        """
        if not self.config.auto_cleanup:
            logger.info("Auto-cleanup is disabled")
            return 0

        if target_free_gb is None:
            target_free_gb = self.config.min_free_space_gb

        files_deleted = 0
        video_files = self.get_video_files(self.config.recording_dir)

        logger.info(f"Starting cleanup: {len(video_files)} video files in recordings")

        for file_path, mod_time in video_files:
            # Check if we've met storage limits
            if self.check_storage_limits():
                break

            try:
                # Delete video file
                file_size_mb = file_path.stat().st_size / (1024**2)
                file_path.unlink()
                files_deleted += 1
                logger.info(f"Deleted old file: {file_path.name} ({file_size_mb:.2f} MB)")

                # Also delete associated JSON file if it exists
                json_file = file_path.with_suffix(".json")
                if json_file.exists():
                    json_file.unlink()
                    logger.debug(f"Deleted associated file: {json_file.name}")

            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")

        if files_deleted > 0:
            logger.info(f"Cleanup complete: deleted {files_deleted} files")
        else:
            logger.debug("No files needed to be deleted")

        return files_deleted

    def move_to_buffer(self, file_path: Path) -> bool:
        """
        Move a completed video file to the upload buffer.

        Args:
            file_path: Path to video file

        Returns:
            True if successful, False otherwise
        """
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False

        try:
            dest_path = self.config.buffer_dir / file_path.name
            shutil.move(str(file_path), str(dest_path))
            logger.info(f"Moved to buffer: {file_path.name}")

            # Also move associated JSON file if it exists
            json_file = file_path.with_suffix(".json")
            json_file_name = json_file.name.replace(".mp4", "_detections.json")
            json_source = self.config.recording_dir / json_file_name

            if json_source.exists():
                json_dest = self.config.buffer_dir / json_file_name
                shutil.move(str(json_source), str(json_dest))
                logger.debug(f"Moved detection results: {json_file_name}")

            return True

        except Exception as e:
            logger.error(f"Failed to move file to buffer: {e}")
            return False

    def get_storage_statistics(self) -> dict:
        """Get comprehensive storage statistics."""
        total_gb, used_gb, free_gb = self.get_disk_usage()
        recording_size = self.get_directory_size(self.config.recording_dir)
        buffer_size = self.get_directory_size(self.config.buffer_dir)
        recording_files = len(self.get_video_files(self.config.recording_dir))
        buffer_files = len(self.get_video_files(self.config.buffer_dir))

        return {
            "disk": {
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "free_percent": round((free_gb / total_gb) * 100, 2),
            },
            "recordings": {
                "size_gb": round(recording_size, 2),
                "file_count": recording_files,
            },
            "buffer": {
                "size_gb": round(buffer_size, 2),
                "file_count": buffer_files,
            },
            "limits": {
                "max_storage_gb": self.config.max_storage_gb,
                "min_free_space_gb": self.config.min_free_space_gb,
            },
            "within_limits": self.check_storage_limits(),
        }
