#!/bin/bash
# Script to set up a systemd service for pi_camera.py on the Raspberry Pi

# Load configuration from YAML file using yq
# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo "Error: yq is not installed. Please install it using:"
    echo "  pip install yq"
    exit 1
fi

# Default to Pi 4 configuration
PI_TYPE="pi4"
if [ "$1" == "zero" ]; then
    PI_TYPE="zero"
fi

# Load configuration values
PI_USER=$(yq -r .pi.$PI_TYPE.user config.yaml)
PI_HOST=$(yq -r .pi.$PI_TYPE.host config.yaml)
PI_DEST_DIR=$(yq -r .pi.$PI_TYPE.dest_dir config.yaml)
PI_VENV_DIR=$(yq -r .pi.$PI_TYPE.venv_dir config.yaml)
S3_BUCKET=$(yq -r .aws.s3_bucket config.yaml)
SERVICE_NAME=$(yq -r .service.name config.yaml)

echo "Setting up service on $PI_TYPE at $PI_HOST..."

# Create the systemd service file locally
cat > /tmp/${SERVICE_NAME}.service << EOF
[Unit]
Description=Raspberry Pi Camera Service
After=network.target

[Service]
Type=simple
User=${PI_USER}
WorkingDirectory=${PI_DEST_DIR}
ExecStart=${PI_VENV_DIR}/bin/python3 ${PI_DEST_DIR}/pi_camera.py capture-only --s3-bucket ${S3_BUCKET}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Copy the service file to the Pi
scp /tmp/${SERVICE_NAME}.service ${PI_USER}@${PI_HOST}:/tmp/

# Install the service on the Pi
ssh ${PI_USER}@${PI_HOST} "
    # Move service file to systemd directory (requires sudo)
    sudo mv /tmp/${SERVICE_NAME}.service /etc/systemd/system/
    
    # Reload systemd, enable and start the service
    sudo systemctl daemon-reload
    sudo systemctl enable ${SERVICE_NAME}.service
    sudo systemctl start ${SERVICE_NAME}.service
    
    # Check the status
    sudo systemctl status ${SERVICE_NAME}.service
"

echo "Service setup complete. The camera will now start automatically on boot."
echo "To check the service status: ssh ${PI_USER}@${PI_HOST} 'sudo systemctl status ${SERVICE_NAME}.service'"
echo "To view logs: ssh ${PI_USER}@${PI_HOST} 'sudo journalctl -u ${SERVICE_NAME}.service -f'"