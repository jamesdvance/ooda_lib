"""
Example usage of the inference pipeline.

This script demonstrates how to run the pipeline with custom configuration.
"""
import asyncio
from config import Config, VideoConfig, InferenceConfig, StorageConfig, LoggingConfig
from main import InferencePipeline


async def run_with_custom_config():
    """Run pipeline with custom configuration."""

    # Create custom configuration
    config = Config(
        video=VideoConfig(
            source=0,  # Use default camera (or specify path/URL)
            width=1920,
            height=1080,
            fps=30,
            codec="avc1",  # H.264
            segment_duration=300,  # 5 minutes
        ),
        inference=InferenceConfig(
            enabled=True,
            frame_interval=30,  # Process every 30th frame (1 per second at 30fps)
            batch_size=4,
            confidence_threshold=0.5,
        ),
        storage=StorageConfig(
            recording_dir="/tmp/recordings",  # Change to desired path
            buffer_dir="/tmp/video_buffer",
            max_storage_gb=10.0,
            min_free_space_gb=2.0,
            auto_cleanup=True,
            save_inference_results=True,
        ),
        logging=LoggingConfig(
            log_file="/tmp/inference.log",
            log_level="INFO",
        ),
    )

    # Create and run pipeline
    pipeline = InferencePipeline(config)

    if await pipeline.initialize():
        await pipeline.run()
    else:
        print("Failed to initialize pipeline")


async def run_from_video_file():
    """Run pipeline on a video file instead of live camera."""

    # Load base config from environment
    config = Config.from_env()

    # Override video source to use a file
    config.video.source = "/path/to/your/video.mp4"

    # Disable real-time capture settings for file playback
    config.video.segment_duration = 60  # Shorter segments for testing

    # Run pipeline
    pipeline = InferencePipeline(config)
    if await pipeline.initialize():
        await pipeline.run()


async def run_from_rtsp_stream():
    """Run pipeline from RTSP camera stream."""

    config = Config.from_env()

    # Set RTSP URL
    config.video.source = "rtsp://username:password@192.168.1.100:554/stream"

    # Run pipeline
    pipeline = InferencePipeline(config)
    if await pipeline.initialize():
        await pipeline.run()


if __name__ == "__main__":
    # Choose which example to run:

    # Example 1: Custom configuration
    asyncio.run(run_with_custom_config())

    # Example 2: Process video file
    # asyncio.run(run_from_video_file())

    # Example 3: RTSP stream
    # asyncio.run(run_from_rtsp_stream())
