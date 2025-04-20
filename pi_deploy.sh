#!/bin/bash
# Script to deploy and run the pi_camera.py script on a Raspberry Pi

# Configuration - Modify these variables
PI_USER="james"
PI_HOST="192.168.1.167"  # Change to your Pi's hostname or IP
PI_DEST_DIR="/home/james/ooda_box"
PI_VENV_DIR="/home/james/ooda_box/venv"
S3_BUCKET="your-s3-bucket-name"  # Change to your S3 bucket

# Ensure target directory exists on the Pi
ssh ${PI_USER}@${PI_HOST} "mkdir -p ${PI_DEST_DIR}"

# Copy the script to the Pi
scp "$(dirname "$0")/pi_camera.py" ${PI_USER}@${PI_HOST}:${PI_DEST_DIR}/

# Setup Python environment if it doesn't exist
ssh ${PI_USER}@${PI_HOST} "
    if [ ! -d ${PI_VENV_DIR} ]; then
        echo 'Setting up Python virtual environment...'
        python3 -m venv ${PI_VENV_DIR}
        source ${PI_VENV_DIR}/bin/activate
        pip install --upgrade pip
        pip install boto3
        # Note: picamera2 is typically installed system-wide on Pi OS
        # sudo apt install -y python3-picamera2
    fi
"

# Run the camera script in capture-only mode
echo "Starting camera in capture-only mode on Raspberry Pi..."
ssh -t ${PI_USER}@${PI_HOST} "
    cd ${PI_DEST_DIR}
    source ${PI_VENV_DIR}/bin/activate
    python3 pi_camera.py capture-only --s3-bucket ${S3_BUCKET}
"

echo "Connection to Raspberry Pi terminated."