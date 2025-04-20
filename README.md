# OODA Box - Raspberry Pi Camera Module

A Python module for continuous video capture and S3 upload on Raspberry Pi.

## Features

- 'capture-only' mode: Continuously captures video using the Pi camera
- Saves video in chunks locally (H.264 format for hardware acceleration)
- Periodically uploads video chunks to Amazon S3
- Auto-deletes local files after successful upload
- Can run as a systemd service for automatic startup

## Requirements

- Raspberry Pi with camera module
- Raspberry Pi OS with libcamera support
- Python 3.6+
- AWS account with S3 bucket
- AWS credentials configured

## Installation

1. Clone this repository to your local machine:
   ```
   git clone https://github.com/yourusername/ooda_box.git
   cd ooda_box
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

## Local Testing

You can test the module locally without a Raspberry Pi:

```bash
./run_local.sh
```

This will:
1. Set up a Python virtual environment
2. Install the required dependencies
3. Run the unit tests
4. Start a mock capture session for local testing

## Deployment to Raspberry Pi

1. Configure the deployment script with your Pi's information:
   ```bash
   nano pi_deploy.sh
   # Edit PI_USER, PI_HOST, S3_BUCKET etc.
   ```

2. Deploy to your Raspberry Pi:
   ```bash
   ./pi_deploy.sh
   ```

3. To set up as a systemd service (runs on boot):
   ```bash
   ./pi_setup_service.sh
   ```

## Usage

### On the Raspberry Pi

Manually run the camera module:

```bash
python pi_camera.py capture-only --s3-bucket your-bucket-name
```

Options:
- `--storage`: Local storage path (default: ./videos)
- `--s3-bucket`: S3 bucket name (required for upload)
- `--s3-prefix`: S3 key prefix (default: pi_videos/)

### Managing the Service

If installed as a service:

```bash
# Check status
sudo systemctl status pi-camera

# Stop the service
sudo systemctl stop pi-camera

# Start the service
sudo systemctl start pi-camera

# View logs
sudo journalctl -u pi-camera -f
```

## Design Choices

- **Video Format**: H.264 - Hardware accelerated on Pi, efficient storage
- **Chunk Duration**: 1 minute - Balances file size with recovery in case of failure
- **Upload Interval**: 5 minutes - Reduces API calls while keeping data fresh
- **Threading**: Separate threads for capture and upload to prevent blocking

## License

MIT License