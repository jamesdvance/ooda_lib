#!/bin/bash
# Jetson Nano Security Camera Setup Script
# Run this on your Jetson Nano to set up the recording pipeline

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Check if running on Jetson
check_jetson() {
    if [ ! -f /etc/nv_tegra_release ]; then
        log_warn "This doesn't appear to be a Jetson device. Continuing anyway..."
    else
        log_info "Detected Jetson device"
        cat /etc/nv_tegra_release
    fi
}

# Install system dependencies
install_dependencies() {
    log_step "Installing system dependencies..."
    
    sudo apt update
    sudo apt install -y \
        python3-pip \
        python3-opencv \
        ffmpeg \
        awscli \
        v4l-utils \
        libgstreamer1.0-dev \
        gstreamer1.0-tools \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad
    
    log_info "System dependencies installed"
}

# Install Python packages
install_python_packages() {
    log_step "Installing Python packages..."
    
    pip3 install --upgrade pip
    pip3 install \
        boto3 \
        pyyaml \
        numpy \
        schedule
    
    # OpenCV should already be installed on Jetson, but ensure it's there
    pip3 install opencv-python || log_warn "OpenCV may already be installed via system packages"
    
    log_info "Python packages installed"
}

# Test camera
test_camera() {
    log_step "Testing camera..."
    
    # Check for video devices
    if ls /dev/video* 1> /dev/null 2>&1; then
        log_info "Found video devices:"
        ls -la /dev/video*
    else
        log_warn "No /dev/video* devices found"
    fi
    
    # Try to capture a test frame
    python3 << 'EOF'
import cv2
import sys

# Try different camera sources
sources = [
    0,  # Default USB camera
    "nvarguscamerasrc ! video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12, framerate=30/1 ! nvvidconv ! video/x-raw, format=BGRx ! videoconvert ! video/x-raw, format=BGR ! appsink",
]

for source in sources:
    print(f"Trying source: {source}")
    cap = cv2.VideoCapture(source, cv2.CAP_GSTREAMER if isinstance(source, str) else cv2.CAP_ANY)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"✓ Camera working! Resolution: {frame.shape[1]}x{frame.shape[0]}")
            cv2.imwrite("/tmp/test_frame.jpg", frame)
            print(f"  Test frame saved to /tmp/test_frame.jpg")
            cap.release()
            sys.exit(0)
        cap.release()

print("✗ Could not open any camera source")
sys.exit(1)
EOF
    
    if [ $? -eq 0 ]; then
        log_info "Camera test passed!"
    else
        log_error "Camera test failed. Please check your camera connection."
        exit 1
    fi
}

# Configure AWS
configure_aws() {
    log_step "Configuring AWS credentials..."
    
    if [ -f ~/.aws/credentials ]; then
        log_info "AWS credentials already configured"
        return
    fi
    
    echo ""
    echo "You need to configure AWS credentials for S3 uploads."
    echo "Get your credentials from the AWS Console → IAM → Users → Security credentials"
    echo ""
    
    read -p "Enter AWS Access Key ID: " aws_access_key
    read -p "Enter AWS Secret Access Key: " aws_secret_key
    read -p "Enter AWS Region (e.g., us-west-2): " aws_region
    
    mkdir -p ~/.aws
    cat > ~/.aws/credentials << EOF
[default]
aws_access_key_id = $aws_access_key
aws_secret_access_key = $aws_secret_key
EOF
    
    cat > ~/.aws/config << EOF
[default]
region = $aws_region
output = json
EOF
    
    chmod 600 ~/.aws/credentials
    log_info "AWS credentials configured"
}

# Create S3 bucket
create_s3_bucket() {
    log_step "Setting up S3 bucket..."
    
    # Generate unique bucket name
    BUCKET_NAME="security-cam-$(hostname)-$(date +%Y%m%d)"
    
    echo ""
    read -p "Enter S3 bucket name [$BUCKET_NAME]: " input_bucket
    BUCKET_NAME=${input_bucket:-$BUCKET_NAME}
    
    # Check if bucket exists
    if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
        log_info "Bucket $BUCKET_NAME already exists"
    else
        log_info "Creating bucket: $BUCKET_NAME"
        aws s3 mb "s3://$BUCKET_NAME"
    fi
    
    # Create folder structure
    aws s3api put-object --bucket "$BUCKET_NAME" --key "raw-footage/" || true
    aws s3api put-object --bucket "$BUCKET_NAME" --key "processed/" || true
    aws s3api put-object --bucket "$BUCKET_NAME" --key "annotations/" || true
    aws s3api put-object --bucket "$BUCKET_NAME" --key "models/" || true
    
    # Update config with bucket name
    sed -i "s/your-security-cam-bucket-UNIQUE-ID/$BUCKET_NAME/g" ~/recorder_config.yaml
    sed -i "s/your-security-cam-bucket-UNIQUE-ID/$BUCKET_NAME/g" /etc/systemd/system/security-cam.service 2>/dev/null || true
    
    log_info "S3 bucket configured: $BUCKET_NAME"
    echo "$BUCKET_NAME" > ~/.security_cam_bucket
}

# Install recording scripts
install_scripts() {
    log_step "Installing recording scripts..."
    
    # Copy scripts to home directory
    cp jetson_recorder.py ~/
    cp recorder_config.yaml ~/
    
    chmod +x ~/jetson_recorder.py
    
    # Create recordings directory
    mkdir -p ~/recordings
    
    log_info "Scripts installed to home directory"
}

# Setup systemd service
setup_service() {
    log_step "Setting up systemd service..."
    
    # Update service file with correct username
    CURRENT_USER=$(whoami)
    sed -i "s/User=jetson/User=$CURRENT_USER/g" security-cam.service
    sed -i "s/Group=jetson/Group=$CURRENT_USER/g" security-cam.service
    sed -i "s|/home/jetson|/home/$CURRENT_USER|g" security-cam.service
    
    # Install service
    sudo cp security-cam.service /etc/systemd/system/
    sudo systemctl daemon-reload
    
    log_info "Systemd service installed"
    
    echo ""
    read -p "Start recording service now? [Y/n]: " start_now
    if [[ "$start_now" != "n" && "$start_now" != "N" ]]; then
        sudo systemctl enable security-cam
        sudo systemctl start security-cam
        log_info "Recording service started!"
        
        sleep 3
        sudo systemctl status security-cam --no-pager
    else
        log_info "Service installed but not started."
        echo "Start manually with: sudo systemctl start security-cam"
    fi
}

# Create monitoring script
create_monitor_script() {
    log_step "Creating monitoring tools..."
    
    cat > ~/cam-status.sh << 'EOF'
#!/bin/bash
# Quick status check for security camera

echo "=== Security Camera Status ==="
echo ""

# Service status
echo "Service Status:"
sudo systemctl status security-cam --no-pager | head -20
echo ""

# Recent recordings
echo "Recent Recordings:"
ls -lht ~/recordings/ 2>/dev/null | head -10
echo ""

# Disk usage
echo "Disk Usage:"
df -h ~/ | head -2
echo ""

# S3 sync status
BUCKET=$(cat ~/.security_cam_bucket 2>/dev/null)
if [ -n "$BUCKET" ]; then
    echo "S3 Bucket: $BUCKET"
    echo "Recent uploads:"
    aws s3 ls "s3://$BUCKET/raw-footage/$(date +%Y/%m/%d)/" 2>/dev/null | tail -5
fi
echo ""

# Log tail
echo "Recent Logs:"
sudo tail -20 /var/log/security-cam.log 2>/dev/null || echo "No logs yet"
EOF
    
    chmod +x ~/cam-status.sh
    log_info "Created ~/cam-status.sh for monitoring"
}

# Test S3 upload
test_s3_upload() {
    log_step "Testing S3 upload..."
    
    BUCKET=$(cat ~/.security_cam_bucket 2>/dev/null)
    if [ -z "$BUCKET" ]; then
        log_warn "No bucket configured, skipping S3 test"
        return
    fi
    
    # Create test file
    echo "Test upload $(date)" > /tmp/test_upload.txt
    
    if aws s3 cp /tmp/test_upload.txt "s3://$BUCKET/test_upload.txt"; then
        log_info "S3 upload test successful!"
        aws s3 rm "s3://$BUCKET/test_upload.txt"
    else
        log_error "S3 upload test failed. Check your credentials and bucket permissions."
    fi
    
    rm /tmp/test_upload.txt
}

# Main setup flow
main() {
    echo ""
    echo "=========================================="
    echo "  Jetson Nano Security Camera Setup"
    echo "=========================================="
    echo ""
    
    check_jetson
    
    log_step "This script will:"
    echo "  1. Install required dependencies"
    echo "  2. Test your camera"
    echo "  3. Configure AWS credentials"
    echo "  4. Create S3 bucket"
    echo "  5. Install recording scripts"
    echo "  6. Set up auto-start service"
    echo ""
    
    read -p "Continue? [Y/n]: " continue_setup
    if [[ "$continue_setup" == "n" || "$continue_setup" == "N" ]]; then
        echo "Setup cancelled."
        exit 0
    fi
    
    install_dependencies
    install_python_packages
    test_camera
    configure_aws
    create_s3_bucket
    install_scripts
    test_s3_upload
    create_monitor_script
    setup_service
    
    echo ""
    echo "=========================================="
    echo "  Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Your security camera is now recording!"
    echo ""
    echo "Useful commands:"
    echo "  ~/cam-status.sh          - Check status"
    echo "  sudo systemctl stop security-cam   - Stop recording"
    echo "  sudo systemctl start security-cam  - Start recording"
    echo "  tail -f /var/log/security-cam.log  - View logs"
    echo ""
    echo "Configuration file: ~/recorder_config.yaml"
    echo "Recordings folder:  ~/recordings/"
    echo ""
}

# Run main
main "$@"