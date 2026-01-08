# OODA Edge Inference Module

High-performance video inference pipeline for license plate recognition using FastANPR. Captures video, performs real-time inference, and stores results locally.

## Features

- **Continuous Video Recording**: Records video in segmented files (default 5-minute segments)
- **Real-time License Plate Recognition**: Uses FastANPR (YOLOv8 + PaddleOCR) for detection
- **GPU Acceleration**: Leverages NVIDIA CUDA for fast inference
- **Automatic Storage Management**: Monitors disk space and auto-cleans old files
- **Batch Processing**: Processes frames in batches for optimal performance
- **JSON Output**: Saves detection results alongside video files
- **Configurable**: Environment variable-based configuration

## Architecture

```
┌─────────────────┐
│  Video Source   │ (Camera/RTSP/File)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Video Recorder  │ Captures and segments video
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│Frame Sampling   │ Samples frames at intervals
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│Inference Queue  │ Batches frames for processing
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Model          │ License plate detection & OCR
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│Storage Manager  │ Saves videos + results, cleanup
└─────────────────┘
```

## File Structure

```
inference/
├── main.py           # Main pipeline orchestrator
├── config.py         # Configuration management
├── recorder.py       # Video capture and recording
├── processor.py      # Inference processing (FastANPR)
├── storage.py        # Storage management and cleanup
└── requirements.txt  # Python dependencies
```

## Configuration

Configure via environment variables:

### Video Settings
```bash
OODA_VIDEO_SOURCE=0              # 0=default camera, or path/URL
OODA_VIDEO_WIDTH=1920            # Video width
OODA_VIDEO_HEIGHT=1080           # Video height
OODA_VIDEO_FPS=30                # Frame rate
OODA_VIDEO_CODEC=avc1            # Codec (avc1=H.264, mp4v=MPEG-4)
OODA_SEGMENT_DURATION=300        # Segment duration in seconds
```

### Inference Settings
```bash
OODA_INFERENCE_ENABLED=true      # Enable/disable inference
OODA_FRAME_INTERVAL=30           # Process every Nth frame
OODA_BATCH_SIZE=4                # Batch size for inference
OODA_CONFIDENCE_THRESHOLD=0.5    # Minimum detection confidence
```

### Storage Settings
```bash
OODA_RECORDING_DIR=/data/recordings      # Video storage directory
OODA_BUFFER_DIR=/data/video_buffer       # Upload buffer directory
OODA_MAX_STORAGE_GB=50.0                 # Max storage for recordings
OODA_MIN_FREE_SPACE_GB=5.0               # Min free disk space
OODA_AUTO_CLEANUP=true                   # Auto-delete old files
OODA_SAVE_INFERENCE=true                 # Save detection results
```

### Logging Settings
```bash
OODA_LOG_FILE=/var/log/ooda/inference.log
OODA_LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
```

## Usage

### Run with Docker (Recommended)
```bash
cd /edge
docker-compose up inference
```

### Run Locally
```bash
cd inference/
python main.py
```

## Output

### Video Files
Segmented video files stored in `OODA_RECORDING_DIR`:
```
video_20241209_143022.mp4
video_20241209_143522.mp4
...
```

### Detection Results
JSON files with detection metadata:
```json
{
  "video_file": "video_20241209_143022.mp4",
  "total_detections": 15,
  "total_frames_processed": 600,
  "detections": [
    {
      "frame_number": 30,
      "timestamp": "2024-12-09T14:30:23.123456",
      "plate_text": "ABC1234",
      "confidence": 0.95,
      "bbox": [123.4, 456.7, 234.5, 567.8],
      "polygon": [[x1, y1], [x2, y2], ...]
    }
  ]
}
```

## Performance

### Typical Performance (NVIDIA Jetson/GPU)
- **Video Recording**: 30 FPS @ 1080p
- **Inference Rate**: 1 FPS (30 frame interval)
- **Batch Processing**: 4 frames/batch
- **Storage**: ~1GB per hour (H.264, 1080p)

### Resource Usage
- **CPU**: 2-4 cores
- **Memory**: 2-4 GB
- **GPU**: NVIDIA GPU with CUDA support
- **Storage**: 50 GB (configurable)

## Storage Management

The system automatically manages storage:
1. Monitors disk space continuously
2. Deletes oldest files when limits exceeded
3. Maintains minimum free space
4. Logs all cleanup operations

## Troubleshooting

### No video capture
```bash
# Check video source
ls /dev/video*

# Test camera access
ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 test.jpg
```

### CUDA errors
```bash
# Verify GPU access
nvidia-smi

# Check CUDA installation
python -c "import torch; print(torch.cuda.is_available())"
```

### Storage full
```bash
# Check disk space
df -h /data

# Manual cleanup
rm /data/recordings/video_*.mp4
```

## Development

### Run tests
```bash
pytest tests/
```

### Enable debug logging
```bash
export OODA_LOG_LEVEL=DEBUG
python main.py
```

## Integration

This module integrates with the upload sidecar service:
- Writes videos to shared `/data/video_buffer` volume
- Upload service reads and uploads to cloud storage
- Automatic coordination via Docker volumes

## License

Part of the OODA project.
