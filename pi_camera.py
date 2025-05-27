#!/usr/bin/env python3
"""
Raspberry Pi Camera Module - Video Capture and S3 Upload
Modes:
    - capture-only: Continuously captures video in chunks and uploads to S3
"""

import os
import sys
import time
import argparse
import logging
import datetime
import threading
import queue
import boto3
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('pi_camera')
file_handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

# Constants
VIDEO_CHUNK_DURATION = 60  # seconds (1 minute chunks)
VIDEO_FORMAT = 'h264'  # Hardware accelerated on Pi
S3_UPLOAD_INTERVAL = 300  # seconds (5 minutes)
STORAGE_PATH = Path('videos')

class VideoCapture:
    def __init__(self, mode, storage_path=STORAGE_PATH, 
                 s3_bucket=None, s3_prefix='pi_videos/'):
        self.mode = mode
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True, parents=True)
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.video_queue = queue.Queue()
        self.running = False
        
        # Initialize libcamera
        try:
            import picamera2
            self.camera = picamera2.Picamera2()
            logger.info("Camera initialized successfully")
        except ImportError:
            logger.error("Failed to import picamera2. Make sure libcamera is installed.")
            sys.exit(1)
            
        # Initialize S3 client if bucket provided
        if s3_bucket:
            try:
                self.s3_client = boto3.client('s3')
                logger.info(f"S3 client initialized for bucket: {s3_bucket}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                sys.exit(1)
        else:
            self.s3_client = None
            logger.warning("No S3 bucket provided. Videos will be stored locally only.")

    def start_capture(self):
        """Start video capture in the specified mode"""
        if self.mode == 'capture-only':
            logger.info(f"Starting capture-only mode with {VIDEO_CHUNK_DURATION}s chunks")
            self.running = True
            
            # Start capture thread
            capture_thread = threading.Thread(target=self._capture_video_loop)
            capture_thread.daemon = True
            capture_thread.start()
            
            # Start S3 upload thread if bucket provided
            if self.s3_bucket:
                upload_thread = threading.Thread(target=self._s3_upload_loop)
                upload_thread.daemon = True
                upload_thread.start()
                
            try:
                # Keep main thread alive
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping capture")
                self.stop_capture()
        else:
            logger.error(f"Unsupported mode: {self.mode}")
            
    def stop_capture(self):
        """Stop all capture and upload operations"""
        self.running = False
        logger.info("Stopping capture")
        
    def _capture_video_loop(self):
        """Continuously capture video in chunks"""
        # Configure camera for video
        video_config = self.camera.create_video_configuration()
        self.camera.configure(video_config)
        self.camera.start()
        
        while self.running:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.storage_path / f"video_{timestamp}.{VIDEO_FORMAT}"
            
            try:
                logger.info(f"Starting video chunk: {filepath}")
                
                # Start video recording
                encoder = self.camera.create_encoder()
                encoder.output = str(filepath)
                encoder.start()
                
                # Record for specified duration
                start_time = time.time()
                while time.time() - start_time < VIDEO_CHUNK_DURATION and self.running:
                    time.sleep(0.1)
                
                # Stop recording
                encoder.stop()
                self.camera.stop()
                self.camera.start()
                
                # Add to upload queue
                self.video_queue.put(filepath)
                logger.info(f"Finished video chunk: {filepath}")
                
            except Exception as e:
                logger.error(f"Error during video capture: {e}")
                # Small delay before retrying
                time.sleep(1)
                
                # Try to restart camera if it failed
                try:
                    self.camera.stop()
                    self.camera.configure(video_config)
                    self.camera.start()
                except Exception as restart_error:
                    logger.error(f"Failed to restart camera: {restart_error}")
        
        # Clean up
        try:
            self.camera.stop()
        except:
            pass
        logger.info("Capture loop ended")
    
    def _s3_upload_loop(self):
        """Periodically upload videos to S3 and clean up local files"""
        last_upload_time = time.time()
        files_to_upload = []
        
        while self.running:
            # Get any new files from queue
            try:
                while True:
                    filepath = self.video_queue.get_nowait()
                    files_to_upload.append(filepath)
                    self.video_queue.task_done()
            except queue.Empty:
                pass
                
            # Check if it's time to upload
            current_time = time.time()
            if current_time - last_upload_time >= S3_UPLOAD_INTERVAL or len(files_to_upload) >= 10:
                if files_to_upload:
                    logger.info(f"Starting upload of {len(files_to_upload)} files to S3")
                    
                    for filepath in files_to_upload:
                        if not filepath.exists():
                            logger.warning(f"File doesn't exist, skipping: {filepath}")
                            continue
                            
                        try:
                            # Upload to S3
                            s3_key = f"{self.s3_prefix}{filepath.name}"
                            logger.info(f"Uploading {filepath} to s3://{self.s3_bucket}/{s3_key}")
                            
                            self.s3_client.upload_file(
                                str(filepath), 
                                self.s3_bucket, 
                                s3_key
                            )
                            
                            # Delete local file after successful upload
                            os.remove(filepath)
                            logger.info(f"Uploaded and removed: {filepath}")
                            
                        except Exception as e:
                            logger.error(f"Failed to upload {filepath}: {e}")
                    
                    # Clear the list and update last upload time
                    files_to_upload = []
                    last_upload_time = current_time
            
            # Sleep a bit to prevent CPU hogging
            time.sleep(5)
            
        logger.info("Upload loop ended")

def main():
    parser = argparse.ArgumentParser(description='Raspberry Pi Camera Module')
    parser.add_argument('mode', choices=['capture-only'], 
                        help='Operating mode')
    parser.add_argument('--storage', default=str(STORAGE_PATH),
                        help='Local storage path for videos')
    parser.add_argument('--s3-bucket', 
                        help='S3 bucket name for video uploads')
    parser.add_argument('--s3-prefix', default='pi_videos/',
                        help='S3 key prefix for uploads')
    
    args = parser.parse_args()
    
    capture = VideoCapture(
        mode=args.mode,
        storage_path=args.storage,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix
    )
    
    capture.start_capture()

if __name__ == '__main__':
    main()