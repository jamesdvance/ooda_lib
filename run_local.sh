#!/bin/bash
# Script to run the pi_camera.py locally for testing without actual camera hardware

# Setup Python virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Setting up Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Mock libcamera for local testing
cat > picamera2_mock.py << EOF
"""
Mock picamera2 module for local testing
"""
class Picamera2:
    def __init__(self):
        print("Mock Picamera2 initialized")
        
    def configure(self, config):
        print("Mock camera configured")
        
    def create_video_configuration(self):
        return {}
        
    def start(self):
        print("Mock camera started")
        
    def stop(self):
        print("Mock camera stopped")
        
    def create_encoder(self):
        encoder = MockEncoder()
        return encoder

class MockEncoder:
    def __init__(self):
        self.output = None
        
    def start(self):
        print(f"Mock encoder started: {self.output}")
        # Create a dummy file
        with open(self.output, 'wb') as f:
            f.write(b'dummy video content')
            
    def stop(self):
        print("Mock encoder stopped")
EOF

# Create a .env file for configuration
cat > .env << EOF
# Local development settings
STORAGE_PATH=./test_videos
S3_BUCKET=test-bucket
S3_PREFIX=local-tests/
EOF

# Run the tests
echo "Running unit tests..."
PYTHONPATH=. pytest test_pi_camera.py -v

# Run the camera module in local testing mode
echo -e "\nRunning pi_camera.py in local mode..."
export PYTHONPATH=$(pwd)
export MOCK_CAMERA=1
mkdir -p test_videos

# Run with mock camera
PYTHONPATH=$(pwd) python3 -c "
import os
import sys
import time

# Add mock picamera2 to path
sys.path.insert(0, os.getcwd())
import picamera2_mock
sys.modules['picamera2'] = picamera2_mock

# Import camera module
from pi_camera import VideoCapture

# Create a temp directory for videos
os.makedirs('test_videos', exist_ok=True)

# Run in 'capture-only' mode for 30 seconds
capture = VideoCapture(
    mode='capture-only',
    storage_path='test_videos',
    s3_bucket='local-test-bucket'
)

# Start capture and run for a few seconds
print('Starting mock capture (will run for 30 seconds)...')
capture.running = True

# Start the capture thread
import threading
capture_thread = threading.Thread(target=capture._capture_video_loop)
capture_thread.daemon = True
capture_thread.start()

# Start the S3 upload thread
upload_thread = threading.Thread(target=capture._s3_upload_loop)
upload_thread.daemon = True
upload_thread.start()

# Run for 30 seconds
try:
    for i in range(30):
        print(f'Running... {i+1}/30 seconds')
        time.sleep(1)
    
    # Stop the capture
    capture.running = False
    print('Stopping capture...')
    time.sleep(2)
    
except KeyboardInterrupt:
    capture.running = False
    print('Capture interrupted by user')
"

echo "Local test run complete"