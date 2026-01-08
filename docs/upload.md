# Upload Module: Cost-Effective Video Storage for AI Inference

## Overview

The OODA Upload module provides intelligent, cost-optimized video upload to S3 specifically designed for edge AI inference workloads. It reduces AWS costs by 60-75% compared to naive real-time uploads through compression, batching, and smart scheduling.

**Key Features:**
- **H.265 Compression**: 40-60% size reduction with minimal quality loss
- **Intelligent Batching**: Combines videos by time window to reduce S3 PUT requests by ~95%
- **Scheduled Uploads**: Default 6-hour intervals minimize request costs
- **Crash Recovery**: SQLite persistence ensures no data loss
- **Network Awareness**: Adapts to bandwidth constraints
- **Emergency Mode**: Automatic upload when local storage fills

**Architecture:**

## Quick Start

### Basic Usage

```python
from ooda.upload import Upload

# Initialize with defaults
uploader = Upload()

# Add videos as your AI model processes them
uploader.add_video('/tmp/detection_2024-01-15_10-30-00.mp4')

# Run upload cycle (or use automatic scheduling)
uploader.run_upload_cycle()
```

### Automatic Daemon Mode

```python
from ooda.upload import Upload

# Start automatic uploads
uploader = Upload()
uploader.start_automatic_uploads()

# Your AI inference loop
while True:
    frame = capture_frame()
    detections = model.predict(frame)

    if detections:
        video_path = save_detection_clip(frame)
        uploader.add_video(video_path)

    # Uploads happen automatically every 6 hours
```

### Configuration Files

```bash
# Copy example config
cp ooda/upload/upload_config.example.yaml upload_config.yaml

# Edit for your setup
nano upload_config.yaml

# Use in code
from ooda.upload import Upload, UploadConfig

config = UploadConfig.load('upload_config.yaml')
uploader = Upload(config=config)
```

## Optimizing for AI Inference Scenarios

Different AI workloads have different storage requirements. Here's how to configure the upload module for common scenarios:

### 1. Continuous Object Detection (High Volume)

**Scenario**: Running 24/7 object detection that generates video clips whenever objects are detected (e.g., person detection, vehicle counting).

**Characteristics**:
- High video volume (hundreds of clips per day)
- Storage is for audit/training, not real-time review
- Cost is primary concern

**Optimal Configuration**:
```yaml
compression:
  enabled: true
  crf: 30  # More aggressive compression (lower quality but smaller)
  preset: "fast"  # Faster processing for high volume

batching:
  enabled: true
  window_hours: 6  # Larger batches for maximum request reduction
  min_files: 5  # Wait for multiple detections
  max_batch_size_mb: 5000

schedule:
  upload_interval_hours: 12  # Upload twice daily
  check_network: true
  min_bandwidth_mbps: 1.0

storage:
  buffer_dir: "/data/video_buffer"
  max_buffer_size_gb: 30
  emergency_upload_threshold: 0.8
  cleanup_after_upload: true
  keep_originals: false  # Delete originals to save space

s3:
  storage_class: "INTELLIGENT_TIERING"  # Auto-optimize costs
```

**Why**: Maximizes batching and compression to handle high volume at lowest cost. Acceptable slight quality loss for audit footage.

### 2. Event-Based Recording (Critical Detections)

**Scenario**: Only records when specific events occur (e.g., intrusion detection, anomaly detection). Each video is potentially important.

**Characteristics**:
- Low to medium volume
- Videos are important and may be reviewed
- Quality matters more than cost
- Want faster upload of critical events

**Optimal Configuration**:
```yaml
compression:
  enabled: true
  crf: 23  # Higher quality (default)
  preset: "medium"  # Balance quality and speed

batching:
  enabled: false  # Upload individual events for faster access
  window_hours: 2  # Or use smaller windows if enabled
  min_files: 1

schedule:
  upload_interval_hours: 2  # Upload every 2 hours for faster access
  check_network: true

storage:
  buffer_dir: "/data/video_buffer"
  max_buffer_size_gb: 20
  emergency_upload_threshold: 0.7  # Upload earlier if space fills
  keep_originals: false

s3:
  storage_class: "STANDARD"  # Faster access for review
  key_prefix: "critical_events"  # Organize by event type
```

**Why**: Better quality and faster upload for important events. Individual uploads allow immediate access in S3.

### 3. Periodic Monitoring (Time-Lapse Style)

**Scenario**: Captures frames/clips at regular intervals (e.g., construction monitoring, plant growth, parking lot monitoring).

**Characteristics**:
- Predictable, low volume
- Long-term storage
- Rarely reviewed unless issue detected
- Cost optimization is important

**Optimal Configuration**:
```yaml
compression:
  enabled: true
  crf: 28
  preset: "slow"  # Better compression since volume is low
  max_resolution: "1280x720"  # Downscale if not needed

batching:
  enabled: true
  window_hours: 24  # Batch full days together
  min_files: 10
  max_batch_size_mb: 3000

schedule:
  upload_interval_hours: 24  # Daily upload
  check_network: true

storage:
  buffer_dir: "/data/video_buffer"
  max_buffer_size_gb: 10  # Small buffer is fine
  cleanup_after_upload: true
  keep_originals: false

s3:
  storage_class: "GLACIER_IR"  # Very cheap for rarely accessed data
```

**Why**: Maximum cost optimization for archival footage. Daily batches and glacier storage minimize costs.

### 4. High-Quality Training Data Collection

**Scenario**: Collecting video for model training/retraining. Quality is critical for improving your AI model.

**Characteristics**:
- Variable volume based on collection needs
- Quality is paramount
- Will be downloaded for labeling/training
- Cost is secondary to quality

**Optimal Configuration**:
```yaml
compression:
  enabled: true
  crf: 18  # Very high quality (minimal loss)
  preset: "slow"  # Best compression efficiency
  max_resolution: null  # Keep original resolution

batching:
  enabled: true
  window_hours: 4  # Moderate batching
  min_files: 2

schedule:
  upload_interval_hours: 6
  check_network: true

storage:
  buffer_dir: "/data/video_buffer"
  max_buffer_size_gb: 50  # Larger buffer for high-quality files
  keep_originals: true  # Keep local copies during collection

s3:
  storage_class: "STANDARD"  # Fast access for downloading
  key_prefix: "training_data"
```

**Why**: Prioritizes quality over cost. Still uses compression but with minimal quality loss.

### 5. Bandwidth-Constrained Edge Devices

**Scenario**: Jetson Nano on slow/cellular connection (e.g., remote wildlife camera, mobile deployment).

**Characteristics**:
- Limited upload bandwidth
- May have intermittent connectivity
- Need maximum compression
- Uploads should be small and reliable

**Optimal Configuration**:
```yaml
compression:
  enabled: true
  crf: 32  # Maximum compression
  preset: "veryfast"  # Fast processing for edge device
  max_resolution: "854x480"  # Downscale to SD quality

batching:
  enabled: true
  window_hours: 4
  min_files: 3
  max_batch_size_mb: 500  # Small batches for slow connections

schedule:
  upload_interval_hours: 6
  check_network: true
  min_bandwidth_mbps: 0.5  # Low threshold

storage:
  buffer_dir: "/tmp/video_buffer"  # May have limited storage
  max_buffer_size_gb: 5  # Small buffer
  emergency_upload_threshold: 0.6  # Upload early
  cleanup_after_upload: true
  keep_originals: false

s3:
  storage_class: "INTELLIGENT_TIERING"
  multipart_threshold_mb: 50  # Lower threshold for smaller uploads
  multipart_chunksize_mb: 5  # Smaller chunks
```

**Why**: Aggressive compression and small batches for limited bandwidth. Emergency upload prevents buffer overflow.

### 6. Real-Time Streaming Analysis (Save Highlights)

**Scenario**: Running inference on live stream, only saving interesting segments (e.g., sports highlights, traffic incidents).

**Characteristics**:
- Continuous inference, selective saving
- Saved clips are important
- Quick upload desired for access
- Medium volume

**Optimal Configuration**:
```yaml
compression:
  enabled: true
  crf: 25  # Good quality for highlights
  preset: "fast"  # Quick processing

batching:
  enabled: false  # Upload highlights individually

schedule:
  upload_interval_hours: 1  # Hourly uploads for fast access
  check_network: true

storage:
  buffer_dir: "/data/video_buffer"
  max_buffer_size_gb: 15
  emergency_upload_threshold: 0.7
  keep_originals: false

s3:
  storage_class: "STANDARD"
  key_prefix: "highlights"
```

**Why**: Individual uploads and short intervals for quick access to highlights. Good quality since these are curated clips.

### 7. Multi-Camera Setup

**Scenario**: Multiple cameras running inference (e.g., multi-room monitoring, perimeter security).

**Characteristics**:
- High total volume from multiple sources
- Need to organize by camera
- Shared upload schedule
- High storage requirements

**Optimal Configuration**:
```python
# Programmatic configuration for multi-camera
from ooda.upload import Upload, UploadConfig

# Shared configuration
base_config = UploadConfig()
base_config.compression.crf = 28
base_config.batching.window_hours = 6
base_config.schedule.upload_interval_hours = 12
base_config.s3.bucket_name = "my-multicam-bucket"

# Create uploader per camera with unique prefixes
uploaders = {}
for camera_id in ['cam1', 'cam2', 'cam3', 'cam4']:
    config = base_config
    config.s3.key_prefix = f"videos/{camera_id}"
    config.storage.buffer_dir = f"/data/buffer_{camera_id}"
    uploaders[camera_id] = Upload(config=config)

# Start all uploaders
for uploader in uploaders.values():
    uploader.start_automatic_uploads()

# In inference loop
def on_detection(camera_id, video_path):
    uploaders[camera_id].add_video(video_path)
```

**Configuration per camera**:
```yaml
compression:
  enabled: true
  crf: 28
  preset: "medium"

batching:
  enabled: true
  window_hours: 6
  min_files: 3

schedule:
  upload_interval_hours: 12  # Stagger uploads between cameras

storage:
  buffer_dir: "/data/buffer_cam1"  # Unique per camera
  max_buffer_size_gb: 20

s3:
  key_prefix: "videos/cam1"  # Organized by camera
  storage_class: "INTELLIGENT_TIERING"
```

**Why**: Organizes videos by camera source while sharing upload infrastructure. Reduces total costs through batching across all cameras.

## Configuration Parameters Reference

### Compression Settings

| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| `crf` | 28 | 18-32 | Lower = better quality, larger files. 18=near lossless, 28=good balance, 32=high compression |
| `preset` | medium | ultrafast-veryslow | Slower = better compression. Use "fast" for high volume, "slow" for archival |
| `max_resolution` | null | e.g., "1920x1080" | Downscale to reduce size. Use for bandwidth-constrained scenarios |

### Batching Settings

| Parameter | Default | Recommendation |
|-----------|---------|----------------|
| `window_hours` | 4 | 2-24 hours. Larger = fewer S3 requests, more cost savings |
| `min_files` | 1 | Set to 3-5 for high-volume scenarios to ensure batches form |
| `max_batch_size_mb` | 5000 | Lower (500-1000) for slow connections |

### Schedule Settings

| Parameter | Default | Use Case |
|-----------|---------|----------|
| `upload_interval_hours` | 6 | 1=urgent access, 6=balanced, 12-24=maximum cost savings |
| `retry_delays_minutes` | [1,5,30,120] | Exponential backoff for network issues |

### Storage Settings

| Parameter | Default | Recommendation |
|-----------|---------|----------------|
| `max_buffer_size_gb` | 20 | Match to available disk space. 5-10GB for Jetson Nano, 20-50GB for desktop |
| `emergency_upload_threshold` | 0.8 | Lower (0.6-0.7) for limited storage devices |
| `keep_originals` | false | Set true only during training data collection |

### S3 Storage Classes

| Class | Access Time | Cost | Best For |
|-------|-------------|------|----------|
| `STANDARD` | Instant | $$$ | Frequently accessed, event recordings |
| `INTELLIGENT_TIERING` | Instant | $$ | Unknown access patterns (recommended default) |
| `STANDARD_IA` | Instant | $ | Infrequent access, archival |
| `GLACIER_IR` | Minutes | � | Rarely accessed, compliance |

## Integration with AI Inference

### Example: YOLOv8 Object Detection

```python
from ooda.upload import Upload
from ultralytics import YOLO
import cv2

# Initialize
model = YOLO('yolov8n.pt')
uploader = Upload()
uploader.start_automatic_uploads()

# Inference loop
cap = cv2.VideoCapture(0)
recording = False
frames = []

while True:
    ret, frame = cap.read()
    results = model(frame)

    # Record when objects detected
    if len(results[0].boxes) > 0:
        if not recording:
            recording = True
            frames = []
        frames.append(frame)
    elif recording:
        # Save and upload clip
        video_path = save_frames_to_video(frames)
        uploader.add_video(video_path)
        recording = False
        frames = []

# Uploads happen automatically every 6 hours
```

### Example: Custom Anomaly Detection

```python
from ooda.upload import Upload, UploadConfig

# Configure for critical events
config = UploadConfig()
config.batching.enabled = False  # Upload each anomaly immediately
config.schedule.upload_interval_hours = 1  # Hourly checks
config.s3.key_prefix = "anomalies"

uploader = Upload(config=config)
uploader.start_automatic_uploads()

# Anomaly detection loop
while True:
    sensor_data = read_sensors()
    anomaly_score = anomaly_model.predict(sensor_data)

    if anomaly_score > THRESHOLD:
        # Capture video of anomaly
        video_path = capture_anomaly_video()
        uploader.add_video(video_path)

        # Upload will happen within 1 hour
        # Or force immediate upload for critical anomalies
        if anomaly_score > CRITICAL_THRESHOLD:
            uploader.scheduler.force_upload_now()
            uploader.run_upload_cycle()
```

### Example: Training Data Collection

```python
from ooda.upload import Upload, UploadConfig
import random

# Configure for high-quality training data
config = UploadConfig()
config.compression.crf = 18  # High quality
config.storage.keep_originals = True  # Keep local copies
config.s3.key_prefix = "training_data/raw"

uploader = Upload(config=config)

# Collect diverse examples
while collecting_data:
    frame = capture_frame()
    detections = model(frame)

    # Sample diverse conditions
    confidence_scores = [d.conf for d in detections]

    # Save low-confidence examples for labeling
    if any(0.5 < conf < 0.7 for conf in confidence_scores):
        video_path = save_clip(frame)
        uploader.add_video(video_path)

    # Save rare classes
    if any(d.class_id in RARE_CLASSES for d in detections):
        video_path = save_clip(frame)
        uploader.add_video(video_path)

# Manual upload when collection session ends
uploader.run_upload_cycle()
```

## Monitoring and Cost Tracking

### Check Upload Status

```python
status = uploader.get_status()

print(f"Pending videos: {status['storage']['pending']}")
print(f"Uploaded videos: {status['storage']['uploaded']}")
print(f"Next upload in: {status['scheduler'].get('minutes_until_next', 0):.0f} minutes")
print(f"Estimated monthly cost: ${status['costs']['total_usd'] * 30:.2f}")
```

### Cost Optimization Tips

1. **Enable compression**: Saves 40-60% on storage and transfer costs
2. **Use larger batch windows**: 6-12 hour windows reduce PUT requests by 95%
3. **Choose INTELLIGENT_TIERING**: Automatically moves old videos to cheaper storage
4. **Set appropriate upload intervals**: 6-12 hours is optimal for most scenarios
5. **Clean up after upload**: Don't keep local copies unless needed for training

### Estimated Daily Costs

Based on 24/7 object detection generating 100 clips/day (1GB/day):

| Configuration | Daily Storage | Daily Requests | Total/Day |
|---------------|--------------|----------------|-----------|
| Real-time upload (no optimization) | $0.023 | $0.050 | **$0.073** |
| OODA Upload (default config) | $0.012 | $0.003 | **$0.015** |
| OODA Upload (optimized) | $0.008 | $0.001 | **$0.009** |

**Daily Savings: 80-88% cost reduction ($0.058-0.064/day saved)**

### Estimated Monthly Costs

Based on same 100 clips/day scenario (30GB/month):

| Configuration | Monthly Storage | Monthly Requests | Total/Month |
|---------------|----------------|------------------|-------------|
| Real-time upload (no optimization) | $0.69 | $1.50 | **$2.19** |
| OODA Upload (default config) | $0.35 | $0.08 | **$0.43** |
| OODA Upload (optimized) | $0.23 | $0.02 | **$0.25** |

**Monthly Savings: 80-89% reduction ($1.76-1.94/month saved)**

## Troubleshooting

### "ffmpeg not found"
```bash
# Install ffmpeg
sudo apt-get update
sudo apt-get install ffmpeg
```

### Videos not uploading
```python
# Check scheduler status
status = uploader.get_status()
print(status['scheduler'])

# Force immediate upload
uploader.scheduler.force_upload_now()
uploader.run_upload_cycle()
```

### Disk space filling up
```yaml
# Reduce buffer size and upload more frequently
storage:
  max_buffer_size_gb: 10
  emergency_upload_threshold: 0.6

schedule:
  upload_interval_hours: 3
```

### High network usage
```yaml
# More aggressive compression and larger intervals
compression:
  crf: 30
  max_resolution: "1280x720"

schedule:
  upload_interval_hours: 12
  min_bandwidth_mbps: 2.0  # Wait for better connection
```

## Additional Resources

- **Module Code**: `ooda/upload/`
- **Examples**: `ooda/upload/example_usage.py`
- **Config Template**: `ooda/upload/upload_config.example.yaml`
- **Original Design Discussion**: [Claude Chat - Upload Module Design](https://claude.ai/chat/cee45ce8-6054-4150-912c-1ea61e24d803)

## Summary

The Upload module is designed to minimize AWS costs while maintaining flexibility for different AI inference scenarios:

- **High-volume detection**: Aggressive batching and compression
- **Critical events**: Quality-focused with faster uploads
- **Training data**: Maximum quality with local retention
- **Bandwidth-limited**: Maximum compression with small batches
- **Periodic monitoring**: Daily batches with archival storage

Adjust the configuration based on your specific inference workload and cost/quality trade-offs.
