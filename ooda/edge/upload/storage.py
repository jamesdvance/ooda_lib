import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .models import VideoRecord, VideoStatus, BatchRecord
from .config import StorageConfig
from .utils import get_disk_usage, ensure_dir_exists, safe_delete_file


class StorageManager:
    """
    Manages local video storage, queue, and persistence
    Uses SQLite for crash recovery and state management
    """

    def __init__(self, config: StorageConfig):
        self.config = config
        self.buffer_dir = Path(config.buffer_dir)
        self.processed_dir = self.buffer_dir / "processed"
        self.batches_dir = self.buffer_dir / "batches"
        self.db_path = self.buffer_dir / "upload_state.db"

        # Ensure directories exist
        ensure_dir_exists(self.buffer_dir)
        ensure_dir_exists(self.processed_dir)
        ensure_dir_exists(self.batches_dir)

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for state persistence"""
        with self._get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    original_path TEXT NOT NULL,
                    processed_path TEXT,
                    metadata TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    upload_attempts INTEGER DEFAULT 0,
                    last_error TEXT,
                    s3_key TEXT,
                    batch_id TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY,
                    video_ids TEXT NOT NULL,
                    batch_path TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    total_size INTEGER NOT NULL,
                    video_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    s3_key TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_video_status ON videos(status)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_video_batch ON videos(batch_id)
            """)

            conn.commit()

    @contextmanager
    def _get_db(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def add_video(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> VideoRecord:
        """
        Add a video to the upload queue

        Args:
            file_path: Path to video file
            metadata: Optional metadata dictionary

        Returns:
            VideoRecord object
        """
        video_id = str(uuid.uuid4())
        now = datetime.utcnow()

        video = VideoRecord(
            id=video_id,
            original_path=file_path,
            status=VideoStatus.PENDING,
            created_at=now,
            updated_at=now
        )

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO videos (id, original_path, processed_path, metadata, status,
                                  created_at, updated_at, upload_attempts, last_error, s3_key, batch_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                video.id,
                video.original_path,
                video.processed_path,
                json.dumps(metadata) if metadata else None,
                video.status.value,
                video.created_at.isoformat(),
                video.updated_at.isoformat(),
                video.upload_attempts,
                video.last_error,
                video.s3_key,
                video.batch_id
            ))
            conn.commit()

        return video

    def update_video(self, video: VideoRecord):
        """Update video record in database"""
        video.updated_at = datetime.utcnow()

        with self._get_db() as conn:
            conn.execute("""
                UPDATE videos
                SET processed_path = ?, status = ?, updated_at = ?,
                    upload_attempts = ?, last_error = ?, s3_key = ?, batch_id = ?
                WHERE id = ?
            """, (
                video.processed_path,
                video.status.value,
                video.updated_at.isoformat(),
                video.upload_attempts,
                video.last_error,
                video.s3_key,
                video.batch_id,
                video.id
            ))
            conn.commit()

    def get_video(self, video_id: str) -> Optional[VideoRecord]:
        """Get video record by ID"""
        with self._get_db() as conn:
            row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
            if row:
                return self._row_to_video(row)
        return None

    def get_videos_by_status(self, status: VideoStatus) -> List[VideoRecord]:
        """Get all videos with given status"""
        with self._get_db() as conn:
            rows = conn.execute("SELECT * FROM videos WHERE status = ?", (status.value,)).fetchall()
            return [self._row_to_video(row) for row in rows]

    def get_pending_videos(self, limit: Optional[int] = None) -> List[VideoRecord]:
        """Get pending videos for processing"""
        query = "SELECT * FROM videos WHERE status = ? ORDER BY created_at ASC"
        if limit:
            query += f" LIMIT {limit}"

        with self._get_db() as conn:
            rows = conn.execute(query, (VideoStatus.PENDING.value,)).fetchall()
            return [self._row_to_video(row) for row in rows]

    def get_ready_videos(self) -> List[VideoRecord]:
        """Get videos ready for upload"""
        return self.get_videos_by_status(VideoStatus.READY)

    def delete_video(self, video_id: str):
        """Delete video record from database"""
        with self._get_db() as conn:
            conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            conn.commit()

    def add_batch(self, batch: BatchRecord):
        """Add batch record to database"""
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO batches (id, video_ids, batch_path, start_time, end_time,
                                   total_size, video_count, created_at, status, s3_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                batch.id,
                json.dumps(batch.video_ids),
                batch.batch_path,
                batch.start_time.isoformat(),
                batch.end_time.isoformat(),
                batch.total_size,
                batch.video_count,
                batch.created_at.isoformat(),
                batch.status.value,
                batch.s3_key
            ))
            conn.commit()

    def update_batch(self, batch: BatchRecord):
        """Update batch record in database"""
        with self._get_db() as conn:
            conn.execute("""
                UPDATE batches
                SET status = ?, s3_key = ?
                WHERE id = ?
            """, (batch.status.value, batch.s3_key, batch.id))
            conn.commit()

    def get_batch(self, batch_id: str) -> Optional[BatchRecord]:
        """Get batch record by ID"""
        with self._get_db() as conn:
            row = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
            if row:
                return self._row_to_batch(row)
        return None

    def get_ready_batches(self) -> List[BatchRecord]:
        """Get batches ready for upload"""
        with self._get_db() as conn:
            rows = conn.execute("SELECT * FROM batches WHERE status = ?",
                              (VideoStatus.READY.value,)).fetchall()
            return [self._row_to_batch(row) for row in rows]

    def _row_to_video(self, row: sqlite3.Row) -> VideoRecord:
        """Convert database row to VideoRecord"""
        return VideoRecord(
            id=row['id'],
            original_path=row['original_path'],
            processed_path=row['processed_path'],
            metadata=json.loads(row['metadata']) if row['metadata'] else None,
            status=VideoStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            upload_attempts=row['upload_attempts'],
            last_error=row['last_error'],
            s3_key=row['s3_key'],
            batch_id=row['batch_id']
        )

    def _row_to_batch(self, row: sqlite3.Row) -> BatchRecord:
        """Convert database row to BatchRecord"""
        return BatchRecord(
            id=row['id'],
            video_ids=json.loads(row['video_ids']),
            batch_path=row['batch_path'],
            start_time=datetime.fromisoformat(row['start_time']),
            end_time=datetime.fromisoformat(row['end_time']),
            total_size=row['total_size'],
            video_count=row['video_count'],
            created_at=datetime.fromisoformat(row['created_at']),
            status=VideoStatus(row['status']),
            s3_key=row['s3_key']
        )

    def get_disk_usage(self) -> Dict[str, Any]:
        """Get current disk usage statistics"""
        return get_disk_usage(str(self.buffer_dir))

    def is_storage_critical(self) -> bool:
        """Check if storage is above emergency threshold"""
        usage = self.get_disk_usage()
        return usage['percent_used'] >= (self.config.emergency_upload_threshold * 100)

    def cleanup_uploaded_files(self):
        """Clean up local files that have been successfully uploaded"""
        if not self.config.cleanup_after_upload:
            return

        uploaded_videos = self.get_videos_by_status(VideoStatus.UPLOADED)

        for video in uploaded_videos:
            # Delete processed file if it exists
            if video.processed_path and not self.config.keep_originals:
                if safe_delete_file(video.processed_path):
                    video.mark_archived()
                    self.update_video(video)

            # Delete original if we're not keeping originals
            if not self.config.keep_originals:
                if safe_delete_file(video.original_path):
                    video.mark_archived()
                    self.update_video(video)

    def cleanup_failed_files(self, max_age_hours: int = 48):
        """Clean up files from failed uploads older than max_age_hours"""
        with self._get_db() as conn:
            cutoff = datetime.utcnow()
            rows = conn.execute("""
                SELECT * FROM videos
                WHERE status = ? AND updated_at < ?
            """, (VideoStatus.FAILED.value, (cutoff.timestamp() - max_age_hours * 3600))).fetchall()

            for row in rows:
                video = self._row_to_video(row)
                safe_delete_file(video.original_path)
                if video.processed_path:
                    safe_delete_file(video.processed_path)
                self.delete_video(video.id)

    def get_statistics(self) -> Dict[str, Any]:
        """Get storage and queue statistics"""
        with self._get_db() as conn:
            stats = {
                'total_videos': conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0],
                'pending': conn.execute("SELECT COUNT(*) FROM videos WHERE status = ?",
                                      (VideoStatus.PENDING.value,)).fetchone()[0],
                'processing': conn.execute("SELECT COUNT(*) FROM videos WHERE status = ?",
                                         (VideoStatus.PROCESSING.value,)).fetchone()[0],
                'ready': conn.execute("SELECT COUNT(*) FROM videos WHERE status = ?",
                                    (VideoStatus.READY.value,)).fetchone()[0],
                'uploading': conn.execute("SELECT COUNT(*) FROM videos WHERE status = ?",
                                        (VideoStatus.UPLOADING.value,)).fetchone()[0],
                'uploaded': conn.execute("SELECT COUNT(*) FROM videos WHERE status = ?",
                                       (VideoStatus.UPLOADED.value,)).fetchone()[0],
                'failed': conn.execute("SELECT COUNT(*) FROM videos WHERE status = ?",
                                     (VideoStatus.FAILED.value,)).fetchone()[0],
                'total_batches': conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0],
                'disk_usage': self.get_disk_usage()
            }

        return stats
