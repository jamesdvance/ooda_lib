#!/bin/bash
# Script to deploy and run the pi_camera.py script on a Raspberry Pi

# Load configuration from YAML file using yq
# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo "Error: yq is not installed. Please install it using:"
    echo "  pip install yq"
    exit 1
fi

# Default to Pi Zero configuration
PI_TYPE="zero"
if [ "$1" == "pi4" ]; then
    PI_TYPE="pi4"
fi

# Load configuration values
PI_USER=$(yq -r .pi.$PI_TYPE.user config.yaml)
PI_HOST=$(yq -r .pi.$PI_TYPE.host config.yaml)
PI_DEST_DIR=$(yq -r .pi.$PI_TYPE.dest_dir config.yaml)
PI_VENV_DIR=$(yq -r .pi.$PI_TYPE.venv_dir config.yaml)
S3_BUCKET=$(yq -r .aws.s3_bucket config.yaml)

echo "Deploying to $PI_TYPE at $PI_HOST..."

# Ensure target directory exists on the Pi
ssh ${PI_USER}@${PI_HOST} "mkdir -p ${PI_DEST_DIR}"

# Copy the script to the Pi
scp "$(dirname "$0")/pi_camera.py" ${PI_USER}@${PI_HOST}:${PI_DEST_DIR}/


# Install to global python environment
ssh ${PI_USER}@${PI_HOST} "
    if [ ! -d ${PI_VENV_DIR} ]; then
        pip install --upgrade pip
        pip install boto3
        # Note: picamera2 is typically installed system-wide on Pi OS
        sudo apt install -y python3-picamera2
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