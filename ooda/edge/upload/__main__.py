#!/usr/bin/env python3
"""
OODA Upload Module - Main entry point for running as a module
Usage: python -m upload [command]
"""

import sys
import time
import signal
import logging
from pathlib import Path

from .upload import Upload
from .config import UploadConfig

logger = logging.getLogger(__name__)


def run_daemon():
    """Run upload daemon with automatic scheduled uploads"""
    print("OODA Upload Daemon Starting...")
    
    # Load configuration from file or environment
    config_path = Path("upload_config.yaml")
    if config_path.exists():
        config = UploadConfig.load(str(config_path))
        print(f"Loaded configuration from {config_path}")
    else:
        config = UploadConfig.load()
        print("Using default configuration (override with environment variables)")
    
    # Initialize uploader
    uploader = Upload(config=config)
    
    # Print startup information
    print(f"\nConfiguration:")
    print(f"  S3 Bucket: {config.s3.bucket_name}")
    print(f"  Buffer Directory: {config.storage.buffer_dir}")
    print(f"  Upload Interval: {config.schedule.upload_interval_hours}h")
    print(f"  Compression: {'enabled' if config.compression.enabled else 'disabled'}")
    print(f"  Batching: {'enabled' if config.batching.enabled else 'disabled'}")
    print(f"  Log Level: {config.monitoring.log_level}")
    print()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutdown signal received, stopping daemon...")
        uploader.stop_automatic_uploads()
        uploader.cleanup()
        print("Daemon stopped")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start automatic uploads
    uploader.start_automatic_uploads()
    print("Daemon started - waiting for videos and scheduled uploads")
    print("Press Ctrl+C to stop\n")
    
    try:
        # Keep daemon running and monitor status
        while True:
            status = uploader.get_status()
            
            # Log status periodically
            if status['storage']['pending'] > 0 or status['storage']['ready'] > 0:
                logger.info(
                    f"Status - Pending: {status['storage']['pending']}, "
                    f"Ready: {status['storage']['ready']}, "
                    f"Uploaded: {status['storage']['uploaded']}"
                )
            
            # Check disk usage
            disk_usage = status['storage']['disk_usage']['percent_used']
            if disk_usage > 70:
                logger.warning(f"High disk usage: {disk_usage:.1f}%")
            
            # Wait before next status check
            time.sleep(300)  # Check every 5 minutes
    
    except KeyboardInterrupt:
        pass
    finally:
        uploader.stop_automatic_uploads()
        uploader.cleanup()
        print("Daemon stopped")


def run_once():
    """Run upload cycle once and exit"""
    print("Running single upload cycle...")
    
    config = UploadConfig.load()
    uploader = Upload(config=config)
    
    success = uploader.run_upload_cycle()
    
    status = uploader.get_status()
    print(f"\nUpload cycle {'completed successfully' if success else 'failed'}")
    print(f"Status: {status['storage']}")
    
    sys.exit(0 if success else 1)


def show_status():
    """Show current upload system status"""
    config = UploadConfig.load()
    uploader = Upload(config=config)
    
    status = uploader.get_status()
    
    print("\n=== OODA Upload System Status ===\n")
    
    print("Storage Statistics:")
    for key, value in status['storage'].items():
        if key != 'disk_usage':
            print(f"  {key}: {value}")
    
    print("\nDisk Usage:")
    disk = status['storage']['disk_usage']
    print(f"  Directory: {disk['directory_size_gb']:.2f} GB")
    print(f"  Used: {disk['percent_used']:.1f}%")
    print(f"  Available: {disk['available_gb']:.2f} GB")
    
    print("\nScheduler:")
    for key, value in status['scheduler'].items():
        print(f"  {key}: {value}")
    
    print("\nConfiguration:")
    for key, value in status['config'].items():
        print(f"  {key}: {value}")
    
    if status['costs']:
        print(f"\nEstimated Costs: ${status['costs']:.4f}")
    
    print()


def show_help():
    """Show help message"""
    print("""
OODA Upload Module

Usage:
  python -m upload [command]

Commands:
  daemon      Run as daemon with automatic scheduled uploads (default)
  once        Run single upload cycle and exit
  status      Show current system status
  help        Show this help message

Environment Variables:
  OODA_S3_BUCKET              S3 bucket name
  OODA_S3_REGION              AWS region
  OODA_BUFFER_DIR             Local buffer directory
  OODA_LOG_LEVEL              Log level (DEBUG, INFO, WARNING, ERROR)
  OODA_LOG_FILE               Log file path
  AWS_ACCESS_KEY_ID           AWS access key
  AWS_SECRET_ACCESS_KEY       AWS secret key

Configuration:
  Place upload_config.yaml in current directory to customize settings.
  See upload_config.example.yaml for reference.

Examples:
  python -m upload daemon
  python -m upload once
  python -m upload status
""")


def main():
    """Main entry point"""
    commands = {
        'daemon': run_daemon,
        'once': run_once,
        'status': show_status,
        'help': show_help,
    }
    
    # Get command from arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = 'daemon'  # Default to daemon mode
    
    # Execute command
    if command in commands:
        commands[command]()
    else:
        print(f"Unknown command: {command}")
        show_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
