#!/usr/bin/env python3
"""
Unit tests for pi_camera.py module
"""
import os
import sys
import time
import unittest
import tempfile
import threading
from unittest.mock import patch, MagicMock, ANY
from pathlib import Path

import boto3
import moto

# Import the module to test
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from pi_camera import VideoCapture

class TestPiCamera(unittest.TestCase):
    """Test suite for the pi_camera module"""
    
    @patch('pi_camera.picamera2')
    def setUp(self, mock_picamera2):
        """Set up test environment"""
        # Create a temp directory for video storage
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name)
        
        # Mock the Picamera2 class
        self.mock_camera = MagicMock()
        self.mock_encoder = MagicMock()
        mock_picamera2.Picamera2.return_value = self.mock_camera
        self.mock_camera.create_encoder.return_value = self.mock_encoder
        
        # Prepare mocked S3 environment
        self.s3_mock = moto.mock_s3()
        self.s3_mock.start()
        self.s3_client = boto3.client('s3')
        self.bucket_name = 'test-bucket'
        self.s3_client.create_bucket(Bucket=self.bucket_name)
        
        # Create test instance with mocked dependencies
        self.capture = VideoCapture(
            mode='capture-only',
            storage_path=self.storage_path,
            s3_bucket=self.bucket_name,
            s3_prefix='test/'
        )
        
        # Replace real S3 client with our mocked version
        self.capture.s3_client = self.s3_client
        
    def tearDown(self):
        """Clean up after tests"""
        self.temp_dir.cleanup()
        self.s3_mock.stop()
    
    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.capture.mode, 'capture-only')
        self.assertEqual(self.capture.storage_path, self.storage_path)
        self.assertEqual(self.capture.s3_bucket, self.bucket_name)
        self.assertEqual(self.capture.s3_prefix, 'test/')
        self.assertFalse(self.capture.running)
    
    @patch('pi_camera.time.sleep', return_value=None)  # Don't actually sleep in tests
    def test_capture_video_flow(self, mock_sleep):
        """Test the video capture flow"""
        # Setup a simulated video file
        test_file = self.storage_path / 'test_video.h264'
        with open(test_file, 'wb') as f:
            f.write(b'dummy video content')
        
        # Mock time.time to control the loop
        original_time = time.time
        time_sequence = [100, 100, 200]  # First stable, then jump forward
        mock_time = MagicMock(side_effect=time_sequence)
        
        with patch('pi_camera.time.time', mock_time):
            with patch.object(self.capture, 'video_queue') as mock_queue:
                # Start capture in a separate thread as it's a loop
                self.capture.running = True
                thread = threading.Thread(target=self.capture._capture_video_loop)
                thread.daemon = True
                thread.start()
                
                # Let it run briefly
                time.sleep(0.1)
                
                # Stop the capture
                self.capture.running = False
                thread.join(timeout=0.5)
                
                # Verify camera operations
                self.mock_camera.configure.assert_called()
                self.mock_camera.start.assert_called()
                
    @patch('pi_camera.time.sleep', return_value=None)
    @patch('pi_camera.os.remove')
    def test_s3_upload_flow(self, mock_remove, mock_sleep):
        """Test the S3 upload flow"""
        # Create test files
        test_files = []
        for i in range(3):
            filepath = self.storage_path / f'test_video_{i}.h264'
            with open(filepath, 'wb') as f:
                f.write(f'test content {i}'.encode())
            test_files.append(filepath)
        
        # Setup time mock to trigger upload
        with patch('pi_camera.time.time', side_effect=[100, 500]):  # Large time gap to trigger upload
            self.capture.running = True
            
            # Add files to queue
            for filepath in test_files:
                self.capture.video_queue.put(filepath)
            
            # Run the upload loop once
            self.capture._s3_upload_loop()
            
            # Verify upload operations
            s3_objects = self.s3_client.list_objects(Bucket=self.bucket_name)
            self.assertIn('Contents', s3_objects)
            self.assertEqual(len(s3_objects['Contents']), 3)
            
            # Verify files were deleted after upload
            self.assertEqual(mock_remove.call_count, 3)
    
    @patch('pi_camera.threading.Thread')
    def test_start_capture(self, mock_thread):
        """Test the start_capture method"""
        # Mock the threads to avoid actually starting them
        mock_capture_thread = MagicMock()
        mock_upload_thread = MagicMock()
        mock_thread.side_effect = [mock_capture_thread, mock_upload_thread]
        
        # Stop after a brief moment
        def set_running_false(*args):
            time.sleep(0.1)
            self.capture.running = False
            
        with patch('pi_camera.time.sleep', side_effect=set_running_false):
            self.capture.start_capture()
            
            # Verify threads started
            self.assertEqual(mock_thread.call_count, 2)
            mock_capture_thread.start.assert_called_once()
            mock_upload_thread.start.assert_called_once()
            self.assertFalse(self.capture.running)
            
    def test_invalid_mode(self):
        """Test invalid mode handling"""
        with patch('pi_camera.logger') as mock_logger:
            capture = VideoCapture(mode='invalid-mode')
            capture.start_capture()
            mock_logger.error.assert_called_with("Unsupported mode: invalid-mode")

if __name__ == '__main__':
    unittest.main()