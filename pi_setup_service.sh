#!/bin/bash
# Script to set up a systemd service for pi_camera.py on the Raspberry Pi

# Configuration - Modify these variables
PI_USER="james"
PI_HOST="192.168.1.167"
PI_DEST_DIR="/home/james/ooda_box"
PI_VENV_DIR="/home/james/ooda_box/venv"
S3_BUCKET="your-s3-bucket-name"  # Change to your S3 bucket
SERVICE_NAME="pi-camera"

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