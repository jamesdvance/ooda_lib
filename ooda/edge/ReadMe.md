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
