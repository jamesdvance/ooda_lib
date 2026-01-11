# Edge - OODA Lib

## Services

### inference
* Performs inference

### upload
* Uploads periodically to the cloud


## Structure

Mimics a 'sidecar' format from K8's. But instead of K8's we'll use Docker compose to keep our edge deployment as lightweight as possible. 

### Folders

jetson-video-inference/
├── docker-compose.yml          # Main orchestration
├── Dockerfile.recorder         # GPU-enabled container for recording + inference
├── Dockerfile.uploader         # Lightweight container for uploads
├── requirements-recorder.txt
├── requirements-uploader.txt
├── update-containers.sh        # Cron script for auto-updates
├── recorder/
│   └── main.py                 # Recording + inference application
└── uploader/
    └── main.py                 # Upload sidecar application

## How to Run

This section provides instructions for setting up and running the OODA edge services.

### 1. Prerequisites Check

Run the installation checker to verify your system has all required dependencies:

```bash
./install.sh
```

This checks for Docker, Docker Compose, NVIDIA Container Runtime, and available disk space. It also creates a `.env.example` template file. If it complains, run through how to install the dependency with AI. We aren't going to try to create a catch-all installation.

### 2. Configuration

Copy and edit the environment configuration file:

```bash
cp .env.example .env
nano .env
```

**Key Environment Variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| **AWS Credentials (Required)** |
| `AWS_ACCESS_KEY_ID` | Your AWS access key | (required) |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | (required) |
| `OODA_S3_BUCKET` | S3 bucket name for uploads | (required) |
| **Video & Inference** |
| `OODA_VIDEO_SOURCE` | Video source (0=camera, path, or RTSP URL) | `0` |
| `OODA_INFERENCE_ENABLED` | Enable license plate recognition | `true` |
| `OODA_FRAME_INTERVAL` | Process every Nth frame | `30` |
| **Storage** |
| `OODA_RECORDING_DIR` | Directory for video recordings | `/data/recordings` |
| `OODA_BUFFER_DIR` | Directory for videos ready to upload | `/data/video_buffer` |
| `OODA_MAX_BUFFER_SIZE_GB` | Maximum buffer size in GB | `20` |
| **Upload** |
| `OODA_UPLOAD_INTERVAL_HOURS` | Hours between uploads | `6` |
| `OODA_COMPRESSION_ENABLED` | Enable H.265 compression | `true` |
| **Logging** |
| `OODA_LOG_LEVEL` | Log verbosity | `INFO` |

### 3. Running with Docker Compose (Recommended)

Use the provided runner script to manage services:

| Command | Description |
|---------|-------------|
| `./run.sh up` | Start services in detached mode |
| `./run.sh logs` | View logs from all services |
| `./run.sh logs inference` | View logs from inference service only |
| `./run.sh status` | Check service status |
| `./run.sh restart` | Restart services |
| `./run.sh down` | Stop services |
| `./run.sh build` | Rebuild Docker images |

The inference service records video with GPU-accelerated license plate recognition, while the uploader service compresses and uploads videos to S3 on a scheduled basis (default every 6 hours).

### 4. Running Manually (Alternative)

If you prefer to run services without Docker:

**Inference Service:**
```bash
cd inference/
pip install -r requirements.txt
python main.py
```
Note: Requires GPU/CUDA for inference functionality.

**Upload Service:**
```bash
cd upload/
pip install -r requirements.txt
sudo apt-get install ffmpeg  # if not already installed
python -m upload daemon      # Run as daemon with scheduled uploads
# OR
python -m upload once        # Run single upload cycle and exit
```

### 5. Verifying It Works

Check that services are running correctly:

```bash
# View all service logs
./run.sh logs

# Check service status
./run.sh status

# Verify video files are being created
ls -lh /data/recordings

# Check upload service status
docker exec -it ooda-uploader python -m upload status
```

Look for log messages indicating the inference service is capturing frames and the upload service is scheduling uploads.
