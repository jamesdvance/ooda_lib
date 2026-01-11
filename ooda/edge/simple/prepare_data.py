#!/usr/bin/env python3
"""
Data Preparation Pipeline
Extracts frames from recorded videos and prepares them for ML training.

Usage:
    python prepare_data.py extract-frames --input s3://bucket/raw-footage/ --output ./frames/
    python prepare_data.py create-dataset --frames ./frames/ --output ./dataset/
    python prepare_data.py sync-to-training --dataset ./dataset/ --dest s3://bucket/training-data/
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import random

try:
    import cv2
    import boto3
    import yaml
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install opencv-python boto3 pyyaml")
    sys.exit(1)


class S3Helper:
    """Helper for S3 operations"""
    
    def __init__(self, bucket: str):
        self.bucket = bucket
        self.s3 = boto3.client('s3')
    
    def list_videos(self, prefix: str = "raw-footage/") -> List[str]:
        """List all video files in bucket"""
        videos = []
        paginator = self.s3.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith(('.mp4', '.avi', '.mkv')):
                    videos.append(obj['Key'])
        
        return videos
    
    def download_file(self, key: str, local_path: str):
        """Download a file from S3"""
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.s3.download_file(self.bucket, key, local_path)
    
    def upload_file(self, local_path: str, key: str):
        """Upload a file to S3"""
        self.s3.upload_file(local_path, self.bucket, key)
    
    def upload_directory(self, local_dir: str, prefix: str):
        """Upload entire directory to S3"""
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, local_dir)
                s3_key = f"{prefix}/{relative_path}"
                self.upload_file(local_path, s3_key)
                print(f"  Uploaded: {s3_key}")


def extract_frames(video_path: str, output_dir: str, 
                   frame_interval: int = 30,
                   max_frames: Optional[int] = None) -> List[str]:
    """Extract frames from a video file"""
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    video_name = Path(video_path).stem
    os.makedirs(output_dir, exist_ok=True)
    
    extracted = []
    frame_count = 0
    saved_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % frame_interval == 0:
            if max_frames and saved_count >= max_frames:
                break
            
            timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            frame_filename = f"{video_name}_frame{frame_count:06d}_{int(timestamp_ms)}ms.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            
            cv2.imwrite(frame_path, frame)
            extracted.append(frame_path)
            saved_count += 1
        
        frame_count += 1
    
    cap.release()
    print(f"Extracted {saved_count} frames from {video_path}")
    return extracted


def extract_motion_frames(video_path: str, output_dir: str,
                          motion_threshold: int = 25,
                          min_area: int = 5000,
                          max_frames: Optional[int] = None) -> List[str]:
    """Extract only frames with motion detected"""
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return []
    
    video_name = Path(video_path).stem
    os.makedirs(output_dir, exist_ok=True)
    
    extracted = []
    prev_gray = None
    frame_count = 0
    saved_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if prev_gray is not None:
            frame_delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(frame_delta, motion_threshold, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            has_motion = any(cv2.contourArea(c) >= min_area for c in contours)
            
            if has_motion:
                if max_frames and saved_count >= max_frames:
                    break
                
                timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                frame_filename = f"{video_name}_motion{frame_count:06d}_{int(timestamp_ms)}ms.jpg"
                frame_path = os.path.join(output_dir, frame_filename)
                
                cv2.imwrite(frame_path, frame)
                extracted.append(frame_path)
                saved_count += 1
        
        prev_gray = gray
        frame_count += 1
    
    cap.release()
    print(f"Extracted {saved_count} motion frames from {video_path}")
    return extracted


def create_yolo_dataset(frames_dir: str, output_dir: str, 
                        train_ratio: float = 0.8,
                        val_ratio: float = 0.1,
                        test_ratio: float = 0.1):
    """Create YOLO-format dataset structure"""
    
    # Create directory structure
    for split in ['train', 'val', 'test']:
        os.makedirs(os.path.join(output_dir, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'labels', split), exist_ok=True)
    
    # Get all frames
    frames = list(Path(frames_dir).glob('*.jpg')) + list(Path(frames_dir).glob('*.png'))
    random.shuffle(frames)
    
    n_total = len(frames)
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)
    
    splits = {
        'train': frames[:n_train],
        'val': frames[n_train:n_train + n_val],
        'test': frames[n_train + n_val:]
    }
    
    for split, split_frames in splits.items():
        for frame_path in split_frames:
            # Copy image
            dest_path = os.path.join(output_dir, 'images', split, frame_path.name)
            shutil.copy(frame_path, dest_path)
            
            # Create empty label file (to be filled during annotation)
            label_path = os.path.join(output_dir, 'labels', split, 
                                      frame_path.stem + '.txt')
            Path(label_path).touch()
        
        print(f"{split}: {len(split_frames)} images")
    
    # Create dataset.yaml
    dataset_yaml = {
        'path': os.path.abspath(output_dir),
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',
        'names': {
            0: 'license_plate',
            1: 'vehicle',
            2: 'person'
        }
    }
    
    yaml_path = os.path.join(output_dir, 'dataset.yaml')
    with open(yaml_path, 'w') as f:
        yaml.dump(dataset_yaml, f, default_flow_style=False)
    
    print(f"\nDataset created at: {output_dir}")
    print(f"Dataset config: {yaml_path}")
    print("\nNext steps:")
    print("1. Annotate images using Label Studio or CVAT")
    print("2. Export annotations in YOLO format")
    print("3. Place label files in the labels/ directories")


def create_annotation_manifest(frames_dir: str, output_file: str):
    """Create a manifest file for annotation tools"""
    
    frames = list(Path(frames_dir).glob('*.jpg')) + list(Path(frames_dir).glob('*.png'))
    
    manifest = []
    for frame_path in frames:
        manifest.append({
            'data': {
                'image': str(frame_path.absolute())
            },
            'predictions': []
        })
    
    with open(output_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"Created annotation manifest: {output_file}")
    print(f"Total images: {len(manifest)}")
    print("\nImport this file into Label Studio or CVAT for annotation")


def main():
    parser = argparse.ArgumentParser(description='Data Preparation Pipeline')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Extract frames command
    extract_parser = subparsers.add_parser('extract-frames', help='Extract frames from videos')
    extract_parser.add_argument('--input', required=True, help='Input video file or S3 path (s3://bucket/prefix/)')
    extract_parser.add_argument('--output', required=True, help='Output directory for frames')
    extract_parser.add_argument('--interval', type=int, default=30, help='Extract every N frames')
    extract_parser.add_argument('--max-frames', type=int, help='Maximum frames to extract per video')
    extract_parser.add_argument('--motion-only', action='store_true', help='Extract only motion frames')
    
    # Create dataset command
    dataset_parser = subparsers.add_parser('create-dataset', help='Create YOLO-format dataset')
    dataset_parser.add_argument('--frames', required=True, help='Directory containing extracted frames')
    dataset_parser.add_argument('--output', required=True, help='Output directory for dataset')
    dataset_parser.add_argument('--train-ratio', type=float, default=0.8)
    dataset_parser.add_argument('--val-ratio', type=float, default=0.1)
    
    # Create manifest command
    manifest_parser = subparsers.add_parser('create-manifest', help='Create annotation manifest')
    manifest_parser.add_argument('--frames', required=True, help='Directory containing frames')
    manifest_parser.add_argument('--output', required=True, help='Output manifest file')
    
    # Sync to S3 command
    sync_parser = subparsers.add_parser('sync-to-s3', help='Sync dataset to S3')
    sync_parser.add_argument('--local', required=True, help='Local directory')
    sync_parser.add_argument('--bucket', required=True, help='S3 bucket name')
    sync_parser.add_argument('--prefix', default='training-data', help='S3 prefix')
    
    args = parser.parse_args()
    
    if args.command == 'extract-frames':
        input_path = args.input
        
        if input_path.startswith('s3://'):
            # Download from S3 first
            parts = input_path[5:].split('/', 1)
            bucket = parts[0]
            prefix = parts[1] if len(parts) > 1 else ''
            
            s3 = S3Helper(bucket)
            videos = s3.list_videos(prefix)
            
            print(f"Found {len(videos)} videos in S3")
            
            temp_dir = '/tmp/video_downloads'
            os.makedirs(temp_dir, exist_ok=True)
            
            for video_key in videos:
                local_video = os.path.join(temp_dir, os.path.basename(video_key))
                print(f"Downloading: {video_key}")
                s3.download_file(video_key, local_video)
                
                if args.motion_only:
                    extract_motion_frames(local_video, args.output, max_frames=args.max_frames)
                else:
                    extract_frames(local_video, args.output, args.interval, args.max_frames)
                
                os.remove(local_video)
        else:
            # Local file or directory
            if os.path.isdir(input_path):
                videos = list(Path(input_path).glob('*.mp4')) + list(Path(input_path).glob('*.avi'))
                for video_path in videos:
                    if args.motion_only:
                        extract_motion_frames(str(video_path), args.output, max_frames=args.max_frames)
                    else:
                        extract_frames(str(video_path), args.output, args.interval, args.max_frames)
            else:
                if args.motion_only:
                    extract_motion_frames(input_path, args.output, max_frames=args.max_frames)
                else:
                    extract_frames(input_path, args.output, args.interval, args.max_frames)
    
    elif args.command == 'create-dataset':
        test_ratio = 1.0 - args.train_ratio - args.val_ratio
        create_yolo_dataset(args.frames, args.output, 
                           args.train_ratio, args.val_ratio, test_ratio)
    
    elif args.command == 'create-manifest':
        create_annotation_manifest(args.frames, args.output)
    
    elif args.command == 'sync-to-s3':
        s3 = S3Helper(args.bucket)
        print(f"Syncing {args.local} to s3://{args.bucket}/{args.prefix}/")
        s3.upload_directory(args.local, args.prefix)
        print("Sync complete!")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()