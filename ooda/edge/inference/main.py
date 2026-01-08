"""
Main entry point for the video inference pipeline.

This module orchestrates video capture, recording, and real-time license plate inference.
"""
import asyncio
import signal
import sys
from pathlib import Path
from loguru import logger

from config import Config
from recorder import VideoRecorder
from processor import InferenceProcessor
from storage import StorageManager


class InferencePipeline:
    """Main pipeline that coordinates recording and inference."""

    def __init__(self, config: Config):
        self.config = config
        self.recorder = VideoRecorder(config.video, config.storage)
        self.processor = InferenceProcessor(config.inference, config.storage)
        self.storage_manager = StorageManager(config.storage)
        self.running = False
        self.frame_count = 0
        self.previous_segment = None

    async def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("Initializing inference pipeline...")

        # Setup logging
        logger.remove()  # Remove default handler
        logger.add(
            sys.stderr,
            level=self.config.logging.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )

        if self.config.logging.log_file:
            self.config.logging.log_file.parent.mkdir(parents=True, exist_ok=True)
            logger.add(
                self.config.logging.log_file,
                rotation=self.config.logging.log_rotation,
                retention=self.config.logging.log_retention,
                level=self.config.logging.log_level,
            )

        # Initialize recorder
        if not self.recorder.start():
            logger.error("Failed to initialize video recorder")
            return False

        # Initialize inference processor
        if not await self.processor.initialize():
            logger.error("Failed to initialize inference processor")
            return False

        # Check storage
        if not self.storage_manager.check_storage_limits():
            logger.warning("Storage limits exceeded, running cleanup...")
            deleted = self.storage_manager.cleanup_old_files()
            logger.info(f"Cleanup removed {deleted} old files")

        logger.info("Inference pipeline initialized successfully")
        return True

    async def run(self):
        """Main processing loop."""
        self.running = True
        logger.info("Starting inference pipeline")

        try:
            while self.running:
                # Read frame from video source
                success, frame = self.recorder.read_frame()

                if not success:
                    logger.warning("Failed to read frame, retrying...")
                    await asyncio.sleep(0.1)
                    continue

                self.frame_count += 1

                # Check if segment changed
                current_segment = self.recorder.get_current_segment_path()
                if current_segment != self.previous_segment and self.previous_segment:
                    # Segment changed - save results for previous segment
                    logger.info(f"Segment completed: {self.previous_segment.name}")
                    self.processor.save_results(self.previous_segment.name)

                    # Check storage and cleanup if needed
                    if not self.storage_manager.check_storage_limits():
                        deleted = self.storage_manager.cleanup_old_files()
                        logger.info(f"Storage cleanup removed {deleted} files")

                self.previous_segment = current_segment

                # Process frame for inference if enabled
                if self.processor.should_process_frame(self.frame_count):
                    self.processor.add_frame(frame, self.frame_count)

                    # Process batch when buffer is full
                    if len(self.processor.frame_buffer) >= self.config.inference.batch_size:
                        await self.processor.process_batch()

                # Log statistics periodically
                if self.frame_count % 1000 == 0:
                    self._log_statistics()

                # Small delay to prevent CPU overload (optional)
                await asyncio.sleep(0.001)

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            await self.shutdown()

    def _log_statistics(self):
        """Log pipeline statistics."""
        stats = self.processor.get_statistics()
        storage_stats = self.storage_manager.get_storage_statistics()

        logger.info(
            f"Pipeline stats: frames={self.frame_count}, "
            f"detections={stats['total_detections']}, "
            f"unique_plates={stats['unique_plates']}, "
            f"disk_free={storage_stats['disk']['free_gb']}GB"
        )

    async def shutdown(self):
        """Cleanup and shutdown all components."""
        logger.info("Shutting down inference pipeline...")
        self.running = False

        # Save any remaining detection results
        if self.previous_segment:
            self.processor.save_results(self.previous_segment.name)

        # Process any remaining frames in buffer
        if self.processor.frame_buffer:
            logger.info("Processing remaining frames in buffer...")
            await self.processor.process_batch()

        # Shutdown components
        self.recorder.stop()
        await self.processor.shutdown()

        # Final statistics
        logger.info(f"Total frames processed: {self.frame_count}")
        final_stats = self.storage_manager.get_storage_statistics()
        logger.info(f"Final storage: {final_stats}")

        logger.info("Pipeline shutdown complete")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False


async def main():
    """Main entry point."""
    # Load configuration from environment
    config = Config.from_env()

    # Create pipeline
    pipeline = InferencePipeline(config)

    # Setup signal handlers
    signal.signal(signal.SIGINT, pipeline.signal_handler)
    signal.signal(signal.SIGTERM, pipeline.signal_handler)

    # Initialize and run
    if await pipeline.initialize():
        await pipeline.run()
    else:
        logger.error("Failed to initialize pipeline")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
