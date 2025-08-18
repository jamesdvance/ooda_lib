

import cv2
import boto3
import os
import datetime
from pathlib import Path
from upload import upload_to_s3

def save(url, s3_bucket_name):
    """
    Saves RTSP stream to cloud location in one-minute chunks
    """
    s3_client = boto3.client('s3')
    temp_dir = Path("/tmp/video_chunks")
    temp_dir.mkdir(exist_ok=True)
    
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        raise Exception(f"Failed to open RTSP stream: {url}")
    
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    chunk_duration = 60
    frames_per_chunk = fps * chunk_duration
    
    chunk_counter = 0
    frame_counter = 0
    current_writer = None
    current_filename = None
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_counter % frames_per_chunk == 0:
                if current_writer:
                    current_writer.release()
                    upload_to_s3(current_filename, s3_client, s3_bucket_name)
                    os.remove(current_filename)
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                current_filename = temp_dir / f"chunk_{timestamp}_{chunk_counter:04d}.mp4"
                current_writer = cv2.VideoWriter(str(current_filename), fourcc, fps, (width, height))
                chunk_counter += 1
            
            current_writer.write(frame)
            frame_counter += 1
            
    except KeyboardInterrupt:
        pass
    finally:
        if current_writer:
            current_writer.release()
            if current_filename and os.path.exists(current_filename):
                upload_to_s3(current_filename, s3_client, s3_bucket_name)
                os.remove(current_filename)
        cap.release()
