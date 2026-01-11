#!/usr/bin/env python3
"""
Jetson Nano Security Camera Recorder
Features:
- Continuous or motion-triggered recording
- Automatic S3 sync
- Disk space management
- Metadata logging for ML training
"""

import cv2
import os
import sys
import time
import json
import yaml
import boto3
import logging
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
from dataclasses import dataclass, asdict
from typing import Optional, Deque
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/security-cam.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class RecordingConfig:
    """Configuration for the recorder"""
    # Camera settings
    camera_id: int = 0
    width: int = 1920
    height: int = 1080
    fps: int = 30
    
    # Recording settings
    output_dir: str = "/home/jetson/recordings"
    segment_duration_seconds: int = 300  # 5 minute segments
    video_codec: str = "h264"  # h264 is hardware accelerated on Jetson
    video_format: str = "mp4"
    
    # Motion detection
    motion_detection_enabled: bool = True
    motion_threshold: int = 25  # Pixel difference threshold
    motion_min_area: int = 5000  # Minimum contour area
    pre_motion_buffer_seconds: int = 5  # Keep N seconds before motion
    post_motion_seconds: int = 10  # Record N seconds after motion stops
    
    # S3 sync settings
    s3_enabled: bool = True
    s3_bucket: str = ""
    s3_prefix: str = "raw-footage"
    s3_sync_interval_seconds: int = 300  # Sync every 5 minutes
    delete_after_sync: bool = True
    
    # Disk management
    max_local_storage_gb: float = 20.0
    min_free_space_gb: float = 2.0
    
    # Metadata
    camera_location: str = "front_yard"
    camera_name: str = "cam_01"


@dataclass
class VideoMetadata:
    """Metadata for each recording segment"""
    filename: str
    start_time: str
    end_time: str
    duration_seconds: float
    camera_name: str
    camera_location: str
    width: int
    height: int
    fps: int
    motion_triggered: bool
    motion_events: int
    file_size_bytes: int


class MotionDetector:
    """Simple motion detection using frame differencing"""
    
    def __init__(self, threshold: int = 25, min_area: int = 5000):
        self.threshold = threshold
        self.min_area = min_area
        self.prev_frame = None
        self.motion_detected = False
        self.motion_regions = []
    
    def detect(self, frame: np.ndarray) -> bool:
        """Detect motion in frame, returns True if motion detected"""
        # Convert to grayscale and blur
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if self.prev_frame is None:
            self.prev_frame = gray
            return False
        
        # Compute difference
        frame_delta = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(frame_delta, self.threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(
            thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        self.motion_regions = []
        motion = False
        
        for contour in contours:
            if cv2.contourArea(contour) >= self.min_area:
                motion = True
                x, y, w, h = cv2.boundingRect(contour)
                self.motion_regions.append((x, y, w, h))
        
        self.prev_frame = gray
        self.motion_detected = motion
        return motion
    
    def get_motion_regions(self):
        """Get bounding boxes of motion regions"""
        return self.motion_regions


class FrameBuffer:
    """Circular buffer to keep pre-motion frames"""
    
    def __init__(self, max_seconds: int, fps: int):
        self.max_frames = max_seconds * fps
        self.buffer: Deque[np.ndarray] = deque(maxlen=self.max_frames)
    
    def add(self, frame: np.ndarray):
        self.buffer.append(frame.copy())
    
    def get_all(self):
        return list(self.buffer)
    
    def clear(self):
        self.buffer.clear()


class S3Uploader:
    """Handles S3 uploads in background thread"""
    
    def __init__(self, bucket: str, prefix: str):
        self.bucket = bucket
        self.prefix = prefix
        self.s3_client = boto3.client('s3')
        self.upload_queue = []
        self.running = False
        self.thread = None
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._upload_worker, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=30)
    
    def queue_upload(self, local_path: str, delete_after: bool = True):
        self.upload_queue.append((local_path, delete_after))
    
    def _upload_worker(self):
        while self.running:
            if self.upload_queue:
                local_path, delete_after = self.upload_queue.pop(0)
                self._upload_file(local_path, delete_after)
            else:
                time.sleep(1)
    
    def _upload_file(self, local_path: str, delete_after: bool):
        try:
            filename = os.path.basename(local_path)
            # Organize by date
            date_prefix = datetime.now().strftime("%Y/%m/%d")
            s3_key = f"{self.prefix}/{date_prefix}/{filename}"
            
            logger.info(f"Uploading {filename} to s3://{self.bucket}/{s3_key}")
            self.s3_client.upload_file(local_path, self.bucket, s3_key)
            
            # Also upload metadata if it exists
            metadata_path = local_path.replace('.mp4', '_metadata.json')
            if os.path.exists(metadata_path):
                metadata_key = s3_key.replace('.mp4', '_metadata.json')
                self.s3_client.upload_file(metadata_path, self.bucket, metadata_key)
                if delete_after:
                    os.remove(metadata_path)
            
            if delete_after:
                os.remove(local_path)
                logger.info(f"Deleted local file: {local_path}")
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")


class JetsonRecorder:
    """Main recorder class for Jetson Nano"""
    
    def __init__(self, config: RecordingConfig):
        self.config = config
        self.running = False
        self.cap = None
        self.writer = None
        self.motion_detector = None
        self.frame_buffer = None
        self.s3_uploader = None
        
        # Recording state
        self.current_segment_path = None
        self.segment_start_time = None
        self.frames_in_segment = 0
        self.motion_events_in_segment = 0
        self.is_motion_recording = False
        self.post_motion_frames = 0
        
        # Create output directory
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
    
    def _init_camera(self):
        """Initialize camera with Jetson-optimized settings"""
        # Try GStreamer pipeline for hardware acceleration
        gst_pipeline = (
            f"nvarguscamerasrc ! "
            f"video/x-raw(memory:NVMM), width={self.config.width}, height={self.config.height}, "
            f"format=NV12, framerate={self.config.fps}/1 ! "
            f"nvvidconv ! video/x-raw, format=BGRx ! "
            f"videoconvert ! video/x-raw, format=BGR ! appsink"
        )
        
        # Try GStreamer first (for CSI cameras)
        self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
        
        if not self.cap.isOpened():
            logger.warning("GStreamer pipeline failed, trying V4L2...")
            # Fallback to V4L2 (for USB cameras)
            self.cap = cv2.VideoCapture(self.config.camera_id)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open camera")
        
        logger.info(f"Camera initialized: {self.config.width}x{self.config.height}@{self.config.fps}fps")
    
    def _init_writer(self, filename: str):
        """Initialize video writer with hardware encoding"""
        filepath = os.path.join(self.config.output_dir, filename)
        
        # Use hardware-accelerated H.264 encoding on Jetson
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        self.writer = cv2.VideoWriter(
            filepath,
            fourcc,
            self.config.fps,
            (self.config.width, self.config.height)
        )
        
        if not self.writer.isOpened():
            raise RuntimeError(f"Failed to create video writer: {filepath}")
        
        self.current_segment_path = filepath
        self.segment_start_time = datetime.now()
        self.frames_in_segment = 0
        self.motion_events_in_segment = 0
        
        logger.info(f"Started recording: {filepath}")
    
    def _close_writer(self):
        """Close current video writer and save metadata"""
        if self.writer is None:
            return
        
        self.writer.release()
        
        # Calculate metadata
        end_time = datetime.now()
        duration = (end_time - self.segment_start_time).total_seconds()
        file_size = os.path.getsize(self.current_segment_path) if os.path.exists(self.current_segment_path) else 0
        
        metadata = VideoMetadata(
            filename=os.path.basename(self.current_segment_path),
            start_time=self.segment_start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            camera_name=self.config.camera_name,
            camera_location=self.config.camera_location,
            width=self.config.width,
            height=self.config.height,
            fps=self.config.fps,
            motion_triggered=self.is_motion_recording,
            motion_events=self.motion_events_in_segment,
            file_size_bytes=file_size
        )
        
        # Save metadata
        metadata_path = self.current_segment_path.replace('.mp4', '_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(asdict(metadata), f, indent=2)
        
        logger.info(f"Closed segment: {self.current_segment_path} ({duration:.1f}s, {file_size/1024/1024:.1f}MB)")
        
        # Queue for S3 upload
        if self.s3_uploader and self.config.s3_enabled:
            self.s3_uploader.queue_upload(
                self.current_segment_path,
                self.config.delete_after_sync
            )
        
        self.writer = None
        self.current_segment_path = None
    
    def _generate_filename(self) -> str:
        """Generate filename for new segment"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.config.camera_name}_{timestamp}.{self.config.video_format}"
    
    def _check_disk_space(self):
        """Check and manage disk space"""
        statvfs = os.statvfs(self.config.output_dir)
        free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
        
        if free_gb < self.config.min_free_space_gb:
            logger.warning(f"Low disk space: {free_gb:.1f}GB free")
            self._cleanup_old_files()
    
    def _cleanup_old_files(self):
        """Remove oldest recordings to free space"""
        recordings = sorted(
            Path(self.config.output_dir).glob("*.mp4"),
            key=lambda p: p.stat().st_mtime
        )
        
        for recording in recordings[:len(recordings)//4]:  # Remove oldest 25%
            metadata_file = str(recording).replace('.mp4', '_metadata.json')
            recording.unlink()
            if os.path.exists(metadata_file):
                os.remove(metadata_file)
            logger.info(f"Cleaned up: {recording}")
    
    def _should_start_new_segment(self) -> bool:
        """Check if we should start a new recording segment"""
        if self.writer is None:
            return True
        
        elapsed = (datetime.now() - self.segment_start_time).total_seconds()
        return elapsed >= self.config.segment_duration_seconds
    
    def run(self):
        """Main recording loop"""
        logger.info("Starting Jetson Recorder...")
        
        try:
            self._init_camera()
            
            if self.config.motion_detection_enabled:
                self.motion_detector = MotionDetector(
                    threshold=self.config.motion_threshold,
                    min_area=self.config.motion_min_area
                )
                self.frame_buffer = FrameBuffer(
                    self.config.pre_motion_buffer_seconds,
                    self.config.fps
                )
            
            if self.config.s3_enabled and self.config.s3_bucket:
                self.s3_uploader = S3Uploader(
                    self.config.s3_bucket,
                    self.config.s3_prefix
                )
                self.s3_uploader.start()
            
            self.running = True
            frame_count = 0
            last_disk_check = time.time()
            
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    logger.error("Failed to read frame")
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                should_record = True
                
                # Motion detection logic
                if self.config.motion_detection_enabled:
                    motion = self.motion_detector.detect(frame)
                    
                    if motion:
                        self.motion_events_in_segment += 1
                        self.post_motion_frames = self.config.post_motion_seconds * self.config.fps
                        
                        if not self.is_motion_recording:
                            logger.info("Motion detected! Starting recording...")
                            self.is_motion_recording = True
                            
                            # Write buffered pre-motion frames
                            if self.writer is None:
                                self._init_writer(self._generate_filename())
                            
                            for buffered_frame in self.frame_buffer.get_all():
                                self.writer.write(buffered_frame)
                                self.frames_in_segment += 1
                            self.frame_buffer.clear()
                    
                    elif self.is_motion_recording:
                        self.post_motion_frames -= 1
                        if self.post_motion_frames <= 0:
                            logger.info("Motion ended, stopping recording...")
                            self.is_motion_recording = False
                            self._close_writer()
                    
                    # Buffer frames when not recording
                    if not self.is_motion_recording:
                        self.frame_buffer.add(frame)
                        should_record = False
                
                # Record frame
                if should_record:
                    if self._should_start_new_segment():
                        self._close_writer()
                        self._init_writer(self._generate_filename())
                    
                    self.writer.write(frame)
                    self.frames_in_segment += 1
                
                # Periodic disk check
                if time.time() - last_disk_check > 60:
                    self._check_disk_space()
                    last_disk_check = time.time()
        
        except KeyboardInterrupt:
            logger.info("Received shutdown signal...")
        except Exception as e:
            logger.error(f"Error in recording loop: {e}")
            raise
        finally:
            self.stop()
    
    def stop(self):
        """Clean shutdown"""
        logger.info("Stopping recorder...")
        self.running = False
        
        self._close_writer()
        
        if self.cap:
            self.cap.release()
        
        if self.s3_uploader:
            self.s3_uploader.stop()
        
        logger.info("Recorder stopped")


def load_config(config_path: str) -> RecordingConfig:
    """Load configuration from YAML file"""
    if os.path.exists(config_path):
        with open(config_path) as f:
            data = yaml.safe_load(f)
        
        return RecordingConfig(**data)
    
    return RecordingConfig()


def main():
    config_path = "/home/jetson/recorder_config.yaml"
    
    # Check for config file argument
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    config = load_config(config_path)
    
    # Override with environment variables if set
    if os.environ.get('S3_BUCKET'):
        config.s3_bucket = os.environ['S3_BUCKET']
    
    recorder = JetsonRecorder(config)
    recorder.run()


if __name__ == "__main__":
    main()