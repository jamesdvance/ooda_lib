# OODA Upload Module

Cost-effective video upload system for S3 designed for edge devices and homebrew computer vision projects.

## Features

- **H.265 Compression**: Reduces file sizes by 40-60% while maintaining quality
- **Intelligent Batching**: Combines videos from configurable time windows (default: 4 hours)
- **Scheduled Uploads**: Uploads every 6 hours by default to minimize S3 request costs
- **Multipart Upload**: Automatic handling of large files with efficient chunking
- **Crash Recovery**: SQLite-based persistence ensures no data loss
- **Network Awareness**: Checks bandwidth availability before uploading
- **Cost Tracking**: Real-time cost estimation for AWS S3 usage
- **Storage Management**: Automatic cleanup and emergency upload triggers


## Installation

### Prerequisites

Required system dependencies:
```bash
# Install ffmpeg for video processing
sudo apt-get update
sudo apt-get install ffmpeg

# Or on macOS
brew install ffmpeg
```

Python dependencies:
```bash
pip install boto3 pyyaml psutil
```

### AWS Configuration

1. Configure AWS credentials:
```bash
aws configure
```

2. Ensure your IAM role has permissions for:
   - `s3:PutObject`
   - `s3:ListBucket`
   - `kms:GenerateDataKey` (if using KMS encryption)

## Quick Start

### Basic Usage

```python
from ooda.upload import Upload

# Initialize with defaults
uploader = Upload()

# Add videos to the queue
uploader.add_video('/path/to/video1.mp4')
uploader.add_video('/path/to/video2.mp4')

# Run upload cycle (process and upload)
uploader.run_upload_cycle()

# Check status
status = uploader.get_status()
print(status)
```

### Automatic Scheduled Uploads

```python
from ooda.upload import Upload
import time

# Start automatic uploads
uploader = Upload()
uploader.start_automatic_uploads()

# Add videos as they're created
uploader.add_video('/path/to/video.mp4')

# Let it run...
time.sleep(3600)

# Stop when done
uploader.stop_automatic_uploads()
```

### Context Manager

```python
from ooda.upload import Upload

with Upload() as uploader:
    uploader.add_video('/path/to/video.mp4')
    uploader.run_upload_cycle()
# Automatic cleanup on exit
```

### Custom Configuration

```python
from ooda.upload import Upload, UploadConfig

# Load from YAML file
config = UploadConfig.load('upload_config.yaml')
uploader = Upload(config=config)

# Or create programmatically
from ooda.upload import UploadConfig, S3Config

config = UploadConfig()
config.s3.bucket_name = 'my-video-bucket'
config.s3.storage_class = 'INTELLIGENT_TIERING'
config.compression.crf = 28
config.schedule.upload_interval_hours = 12

uploader = Upload(config=config)
```

### Environment Variables

Configure via environment variables:
```bash
export OODA_S3_BUCKET=my-video-bucket
export OODA_S3_REGION=us-east-1
export OODA_UPLOAD_INTERVAL_HOURS=6
export OODA_COMPRESSION_CRF=28
export OODA_BUFFER_DIR=/data/video_buffer

python my_upload_script.py
```

## Configuration

Copy the example configuration:
```bash
cp upload_config.example.yaml upload_config.yaml
```

Key configuration options:

### Compression Settings
- `enabled`: Enable/disable compression (default: true)
- `crf`: Quality setting, 18-28 recommended (default: 28)
- `preset`: Speed vs compression trade-off (default: medium)

### Batching Settings
- `window_hours`: Time window for combining videos (default: 4)
- `min_files`: Minimum files per batch (default: 2)
- `max_batch_size_mb`: Maximum batch size (default: 5000)

### Schedule Settings
- `upload_interval_hours`: How often to upload (default: 6)
- `retry_delays_minutes`: Retry backoff delays (default: [1, 5, 30, 120])

### Storage Settings
- `buffer_dir`: Local buffer directory (default: /tmp/ooda_video_buffer)
- `max_buffer_size_gb`: Maximum buffer size (default: 20)
- `cleanup_after_upload`: Delete after upload (default: true)

### S3 Settings
- `bucket_name`: S3 bucket (REQUIRED)
- `storage_class`: Storage tier (default: INTELLIGENT_TIERING)
- `multipart_threshold_mb`: Multipart cutoff (default: 100)

## Advanced Usage

### Manual Processing and Upload

```python
uploader = Upload()

# Add videos
uploader.add_video('/path/to/video.mp4')

# Process videos (compress and batch)
uploader.process_pending_videos()

# Upload when ready
uploader.upload_all()

# Cleanup
uploader.cleanup()
```

### Cost Monitoring

```python
uploader = Upload()
uploader.run_upload_cycle()

# Get cost metrics
status = uploader.get_status()
costs = status['costs']

print(f"Total uploaded: {costs['total_gb_uploaded']} GB")
print(f"Estimated cost: ${costs['total_usd']}")
print(f"Requests: {costs['total_requests']}")
```

### Custom Upload Schedule

```python
uploader = Upload()

# Change upload interval to 12 hours
uploader.scheduler.set_custom_schedule(12)

uploader.start_automatic_uploads()
```

## Architecture

```
Upload
├── StorageManager      # SQLite persistence and queue management
├── VideoProcessor      # Compression and batching with ffmpeg
├── S3Client           # Optimized S3 uploads with multipart support
└── UploadScheduler    # Scheduling and retry logic
```

## Troubleshooting

### ffmpeg not found
Install ffmpeg:
```bash
sudo apt-get install ffmpeg
```

### Permission denied on S3
Check your IAM role permissions:
- Verify `s3:PutObject` permission
- Check KMS permissions if using encryption
- Ensure bucket policy allows your role

### Disk space issues
Adjust buffer settings:
```yaml
storage:
  max_buffer_size_gb: 10  # Reduce buffer size
  emergency_upload_threshold: 0.7  # Upload earlier
```

### Upload failures
Check logs:
```python
uploader = Upload()
# Logs are at /var/log/ooda_upload.log by default
```

Enable debug logging:
```yaml
monitoring:
  log_level: "DEBUG"
```

## Best Practices

1. **Use Intelligent-Tiering storage class**: Automatically optimizes costs
2. **Set appropriate upload interval**: Balance between cost and data freshness
3. **Monitor disk usage**: Ensure enough space for buffering
4. **Enable compression**: Saves 40-60% on storage and transfer
5. **Use batching**: Reduces request costs by ~95%
6. **Set up CloudWatch alarms**: Monitor for failures
7. **Regular cleanup**: Use `uploader.cleanup()` periodically

## License

Part of the OODA Lib project.
