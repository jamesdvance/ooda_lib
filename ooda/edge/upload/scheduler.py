import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable
from threading import Thread, Event

from .config import ScheduleConfig
from .utils import check_network_available

logger = logging.getLogger(__name__)


class UploadScheduler:
    """
    Smart scheduler for managing upload timing and retries
    Implements cost-effective scheduling with network awareness
    """

    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.last_upload = None
        self.next_upload = None
        self.is_running = False
        self.stop_event = Event()
        self.scheduler_thread: Optional[Thread] = None

    def should_upload_now(self) -> bool:
        """
        Determine if upload should happen now based on schedule

        Returns:
            True if it's time to upload
        """
        if self.last_upload is None:
            # First upload, go ahead
            return True

        # Check if enough time has passed
        time_since_last = datetime.utcnow() - self.last_upload
        interval = timedelta(hours=self.config.upload_interval_hours)

        return time_since_last >= interval

    def can_upload(self) -> tuple[bool, str]:
        """
        Check if upload can proceed based on all conditions

        Returns:
            Tuple of (can_upload, reason)
        """
        # Check schedule
        if not self.should_upload_now():
            if self.last_upload:
                next_time = self.last_upload + timedelta(hours=self.config.upload_interval_hours)
                wait_minutes = (next_time - datetime.utcnow()).total_seconds() / 60
                return False, f"Next upload in {wait_minutes:.1f} minutes"
            else:
                return False, "Upload schedule not ready"

        # Check network if configured
        if self.config.check_network:
            if not check_network_available(self.config.min_bandwidth_mbps):
                return False, f"Network unavailable or below {self.config.min_bandwidth_mbps} Mbps"

        return True, "Ready to upload"

    def mark_upload_complete(self):
        """Mark that an upload has completed"""
        self.last_upload = datetime.utcnow()
        self.next_upload = self.last_upload + timedelta(hours=self.config.upload_interval_hours)
        logger.info(f"Upload completed. Next upload scheduled for {self.next_upload}")

    def get_retry_delay(self, attempt: int) -> int:
        """
        Get retry delay in seconds for given attempt number

        Args:
            attempt: Retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        if attempt >= len(self.config.retry_delays_minutes):
            # Use last delay if we exceed configured attempts
            delay_minutes = self.config.retry_delays_minutes[-1]
        else:
            delay_minutes = self.config.retry_delays_minutes[attempt]

        return delay_minutes * 60

    def should_retry(self, attempt: int) -> bool:
        """
        Determine if upload should be retried

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            True if should retry
        """
        return attempt < self.config.max_retries

    def wait_for_retry(self, attempt: int) -> bool:
        """
        Wait for retry delay with interruptible sleep

        Args:
            attempt: Current attempt number

        Returns:
            True if wait completed (not interrupted)
        """
        delay = self.get_retry_delay(attempt)
        logger.info(f"Waiting {delay} seconds before retry {attempt + 1}/{self.config.max_retries}")

        # Use event.wait() for interruptible sleep
        return not self.stop_event.wait(timeout=delay)

    def start_scheduled_uploads(self, upload_callback: Callable[[], bool]):
        """
        Start scheduler thread for automatic uploads

        Args:
            upload_callback: Function to call when upload should happen
        """
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        self.is_running = True
        self.stop_event.clear()

        def scheduler_loop():
            logger.info(f"Upload scheduler started (interval: {self.config.upload_interval_hours}h)")

            while not self.stop_event.is_set():
                try:
                    # Check if upload should happen
                    can_upload, reason = self.can_upload()

                    if can_upload:
                        logger.info("Starting scheduled upload")
                        success = upload_callback()

                        if success:
                            self.mark_upload_complete()
                        else:
                            logger.error("Scheduled upload failed")

                    # Sleep for a check interval (check every 5 minutes)
                    check_interval = 300  # 5 minutes
                    self.stop_event.wait(timeout=check_interval)

                except Exception as e:
                    logger.error(f"Error in scheduler loop: {e}")
                    # Wait before continuing
                    self.stop_event.wait(timeout=60)

            logger.info("Upload scheduler stopped")
            self.is_running = False

        self.scheduler_thread = Thread(target=scheduler_loop, daemon=True)
        self.scheduler_thread.start()

    def stop_scheduled_uploads(self):
        """Stop scheduler thread"""
        if not self.is_running:
            return

        logger.info("Stopping upload scheduler")
        self.stop_event.set()

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10)

        self.is_running = False

    def get_status(self) -> dict:
        """
        Get scheduler status

        Returns:
            Dictionary with status information
        """
        can_upload, reason = self.can_upload()

        status = {
            'is_running': self.is_running,
            'can_upload': can_upload,
            'reason': reason,
            'last_upload': self.last_upload.isoformat() if self.last_upload else None,
            'next_upload': self.next_upload.isoformat() if self.next_upload else None,
            'upload_interval_hours': self.config.upload_interval_hours,
            'check_network': self.config.check_network,
            'min_bandwidth_mbps': self.config.min_bandwidth_mbps
        }

        if self.next_upload:
            time_until_next = self.next_upload - datetime.utcnow()
            status['minutes_until_next'] = max(0, time_until_next.total_seconds() / 60)

        return status

    def force_upload_now(self):
        """
        Force an immediate upload by resetting the schedule
        """
        logger.info("Forcing immediate upload")
        self.last_upload = None
        self.next_upload = None

    def get_next_upload_time(self) -> Optional[datetime]:
        """
        Get next scheduled upload time

        Returns:
            Datetime of next upload, or None if not scheduled
        """
        return self.next_upload

    def estimate_daily_uploads(self) -> int:
        """
        Estimate number of uploads per day based on interval

        Returns:
            Number of uploads per day
        """
        return int(24 / self.config.upload_interval_hours)

    def estimate_monthly_uploads(self) -> int:
        """
        Estimate number of uploads per month

        Returns:
            Number of uploads per month
        """
        return self.estimate_daily_uploads() * 30

    def wait_until_ready(self, check_interval: int = 60) -> bool:
        """
        Wait until upload is ready (blocking)

        Args:
            check_interval: How often to check (seconds)

        Returns:
            True if ready (not interrupted)
        """
        while not self.stop_event.is_set():
            can_upload, reason = self.can_upload()

            if can_upload:
                return True

            logger.debug(f"Waiting for upload: {reason}")
            if self.stop_event.wait(timeout=check_interval):
                # Stop event was set
                return False

        return False

    def set_custom_schedule(self, interval_hours: int):
        """
        Set custom upload interval

        Args:
            interval_hours: Upload interval in hours
        """
        old_interval = self.config.upload_interval_hours
        self.config.upload_interval_hours = interval_hours
        logger.info(f"Upload interval changed from {old_interval}h to {interval_hours}h")

        # Recalculate next upload time
        if self.last_upload:
            self.next_upload = self.last_upload + timedelta(hours=interval_hours)
