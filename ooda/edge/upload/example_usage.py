#!/usr/bin/env python3
"""
Example usage of the OODA Upload module

This script demonstrates various ways to use the upload module
for cost-effective video uploads to S3.
"""

import sys
import time
from pathlib import Path

from upload import Upload, UploadConfig


def example_basic_usage():
    """Basic usage example"""
    print("=== Basic Usage Example ===\n")

    # Initialize uploader with defaults
    uploader = Upload()

    # Add a video
    video_path = "/path/to/video.mp4"  # Change this to your video path
    if Path(video_path).exists():
        video_id = uploader.add_video(video_path)
        print(f"Added video: {video_id}")

        # Run upload cycle
        success = uploader.run_upload_cycle()
        print(f"Upload cycle: {'Success' if success else 'Failed'}")

        # Get status
        status = uploader.get_status()
        print(f"\nStatus: {status}")
    else:
        print(f"Video not found: {video_path}")


def example_automatic_uploads():
    """Automatic scheduled uploads example"""
    print("\n=== Automatic Uploads Example ===\n")

    # Initialize uploader
    uploader = Upload()

    # Start automatic uploads
    uploader.start_automatic_uploads()
    print("Automatic uploads started")

    # Simulate adding videos over time
    try:
        for i in range(5):
            # In real usage, videos would be added as they're created
            video_path = f"/path/to/video{i}.mp4"
            if Path(video_path).exists():
                video_id = uploader.add_video(video_path)
                print(f"Added video {i}: {video_id}")

            # Get scheduler status
            status = uploader.scheduler.get_status()
            print(f"Next upload in {status.get('minutes_until_next', 0):.1f} minutes")

            # Wait before adding next video
            time.sleep(60)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        # Stop automatic uploads
        uploader.stop_automatic_uploads()
        print("Automatic uploads stopped")


def example_custom_config():
    """Custom configuration example"""
    print("\n=== Custom Configuration Example ===\n")

    # Create custom configuration
    config = UploadConfig()

    # Customize S3 settings
    config.s3.bucket_name = "my-video-bucket"
    config.s3.region = "us-west-2"
    config.s3.storage_class = "INTELLIGENT_TIERING"

    # Customize compression
    config.compression.enabled = True
    config.compression.crf = 28  # Good quality, ~50% size reduction
    config.compression.preset = "fast"

    # Customize batching
    config.batching.enabled = True
    config.batching.window_hours = 6  # 6-hour batches
    config.batching.min_files = 3

    # Customize schedule
    config.schedule.upload_interval_hours = 12  # Upload twice per day
    config.schedule.check_network = True
    config.schedule.min_bandwidth_mbps = 2.0

    # Customize storage
    config.storage.buffer_dir = "/data/video_buffer"
    config.storage.max_buffer_size_gb = 50

    # Initialize with custom config
    uploader = Upload(config=config)

    print(f"Configured with:")
    print(f"  S3 Bucket: {config.s3.bucket_name}")
    print(f"  Compression CRF: {config.compression.crf}")
    print(f"  Batch window: {config.batching.window_hours}h")
    print(f"  Upload interval: {config.schedule.upload_interval_hours}h")

    # Use uploader
    uploader.run_upload_cycle()


def example_load_from_file():
    """Load configuration from file example"""
    print("\n=== Load Config from File Example ===\n")

    # Copy upload_config.example.yaml to upload_config.yaml and customize
    config_path = "upload_config.yaml"

    if Path(config_path).exists():
        config = UploadConfig.load(config_path)
        uploader = Upload(config=config)
        print(f"Loaded configuration from {config_path}")

        # Get status
        status = uploader.get_status()
        print(f"Config: {status['config']}")
    else:
        print(f"Config file not found: {config_path}")
        print("Copy upload_config.example.yaml to upload_config.yaml and customize")


def example_context_manager():
    """Context manager usage example"""
    print("\n=== Context Manager Example ===\n")

    with Upload() as uploader:
        # Add videos
        video_path = "/path/to/video.mp4"
        if Path(video_path).exists():
            uploader.add_video(video_path)

        # Run upload cycle
        uploader.run_upload_cycle()

        # Get status
        status = uploader.get_status()
        print(f"Videos uploaded: {status['storage']['uploaded']}")
        print(f"Estimated cost: ${status['costs']['total_usd']}")

    # Automatic cleanup on exit
    print("Context manager cleanup complete")


def example_monitoring():
    """Cost and performance monitoring example"""
    print("\n=== Monitoring Example ===\n")

    uploader = Upload()

    # Add and process some videos
    for i in range(3):
        video_path = f"/path/to/video{i}.mp4"
        if Path(video_path).exists():
            uploader.add_video(video_path)

    # Run upload cycle
    uploader.run_upload_cycle()

    # Get detailed status
    status = uploader.get_status()

    print("Storage Statistics:")
    print(f"  Total videos: {status['storage']['total_videos']}")
    print(f"  Pending: {status['storage']['pending']}")
    print(f"  Ready: {status['storage']['ready']}")
    print(f"  Uploaded: {status['storage']['uploaded']}")
    print(f"  Failed: {status['storage']['failed']}")

    print("\nScheduler Status:")
    print(f"  Running: {status['scheduler']['is_running']}")
    print(f"  Can upload: {status['scheduler']['can_upload']}")
    print(f"  Next upload: {status['scheduler'].get('next_upload', 'Not scheduled')}")

    print("\nCost Metrics:")
    print(f"  Data uploaded: {status['costs']['total_gb_uploaded']} GB")
    print(f"  Data stored: {status['costs']['total_gb_stored']} GB")
    print(f"  Total requests: {status['costs']['total_requests']}")
    print(f"  Estimated cost: ${status['costs']['total_usd']}")

    print("\nDisk Usage:")
    disk = status['storage']['disk_usage']
    print(f"  Buffer directory: {disk['directory_size_gb']:.2f} GB")
    print(f"  Disk usage: {disk['percent_used']:.1f}%")


def example_edge_device_daemon():
    """Example daemon for edge device (e.g., Jetson Nano)"""
    print("\n=== Edge Device Daemon Example ===\n")

    # Load configuration
    config = UploadConfig.load()

    # Override with environment variables if needed
    import os
    if os.getenv('OODA_S3_BUCKET'):
        config.s3.bucket_name = os.getenv('OODA_S3_BUCKET')

    # Initialize uploader
    uploader = Upload(config=config)

    # Start automatic uploads
    uploader.start_automatic_uploads()

    print(f"Upload daemon started")
    print(f"Upload interval: {config.schedule.upload_interval_hours}h")
    print(f"Buffer directory: {config.storage.buffer_dir}")
    print(f"S3 bucket: {config.s3.bucket_name}")

    try:
        # Keep daemon running
        while True:
            # In real usage, this would be triggered by video capture events
            # For now, just monitor status
            status = uploader.get_status()

            if status['storage']['pending'] > 0:
                print(f"Pending videos: {status['storage']['pending']}")

            # Check if storage is getting full
            disk_usage = status['storage']['disk_usage']['percent_used']
            if disk_usage > 70:
                print(f"Warning: Disk usage at {disk_usage:.1f}%")

            # Wait before next check
            time.sleep(300)  # Check every 5 minutes

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        uploader.stop_automatic_uploads()
        uploader.cleanup()
        print("Daemon stopped")


def main():
    """Run all examples"""
    examples = {
        '1': ('Basic Usage', example_basic_usage),
        '2': ('Automatic Uploads', example_automatic_uploads),
        '3': ('Custom Configuration', example_custom_config),
        '4': ('Load from File', example_load_from_file),
        '5': ('Context Manager', example_context_manager),
        '6': ('Monitoring', example_monitoring),
        '7': ('Edge Device Daemon', example_edge_device_daemon),
    }

    if len(sys.argv) > 1:
        choice = sys.argv[1]
        if choice in examples:
            name, func = examples[choice]
            print(f"\nRunning: {name}\n")
            func()
        else:
            print(f"Invalid choice: {choice}")
            print("Available examples:")
            for key, (name, _) in examples.items():
                print(f"  {key}: {name}")
    else:
        print("OODA Upload Module Examples")
        print("=" * 40)
        print("\nAvailable examples:")
        for key, (name, _) in examples.items():
            print(f"  {key}: {name}")
        print(f"\nUsage: {sys.argv[0]} <example_number>")
        print(f"Example: {sys.argv[0]} 1")


if __name__ == '__main__':
    main()
