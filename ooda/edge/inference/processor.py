"""
Inference processor for license plate recognition using FastANPR.
"""
import asyncio
import cv2
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from loguru import logger

from fastanpr import FastANPR
from config import InferenceConfig, StorageConfig


@dataclass
class Detection:
    """License plate detection result."""
    frame_number: int
    timestamp: str
    plate_text: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    polygon: Optional[List[List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class InferenceProcessor:
    """Handles license plate recognition inference on video frames."""

    def __init__(
        self, inference_config: InferenceConfig, storage_config: StorageConfig
    ):
        self.config = inference_config
        self.storage_config = storage_config
        self.model: Optional[FastANPR] = None
        self.frame_buffer: List[cv2.Mat] = []
        self.frame_numbers: List[int] = []
        self.detections: List[Detection] = []
        self.total_frames_processed = 0

    async def initialize(self) -> bool:
        """Initialize the FastANPR model."""
        if not self.config.enabled:
            logger.info("Inference is disabled")
            return True

        try:
            logger.info("Initializing FastANPR model...")
            self.model = FastANPR()
            logger.info("FastANPR model initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize FastANPR model: {e}")
            return False

    def should_process_frame(self, frame_number: int) -> bool:
        """Check if this frame should be processed for inference."""
        if not self.config.enabled:
            return False
        return frame_number % self.config.frame_interval == 0

    def add_frame(self, frame: cv2.Mat, frame_number: int):
        """Add frame to buffer for batch processing."""
        # Convert BGR to RGB (FastANPR expects RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.frame_buffer.append(frame_rgb)
        self.frame_numbers.append(frame_number)

    async def process_batch(self) -> List[Detection]:
        """Process accumulated frames in batch."""
        if not self.frame_buffer or self.model is None:
            return []

        batch_detections = []

        try:
            logger.debug(f"Processing batch of {len(self.frame_buffer)} frames")

            # Run inference on batch
            results = await self.model.run(self.frame_buffer)

            # Process results for each frame
            for frame_idx, plates in enumerate(results):
                frame_number = self.frame_numbers[frame_idx]
                timestamp = datetime.now().isoformat()

                for plate in plates:
                    # Filter by confidence threshold
                    if plate.rec_confidence < self.config.confidence_threshold:
                        continue

                    # Extract bounding box coordinates
                    bbox = [
                        float(plate.det_box[0]),
                        float(plate.det_box[1]),
                        float(plate.det_box[2]),
                        float(plate.det_box[3]),
                    ]

                    # Extract polygon if available
                    polygon = None
                    if hasattr(plate, "polygon") and plate.polygon is not None:
                        polygon = [[float(x), float(y)] for x, y in plate.polygon]

                    detection = Detection(
                        frame_number=frame_number,
                        timestamp=timestamp,
                        plate_text=plate.rec_text,
                        confidence=float(plate.rec_confidence),
                        bbox=bbox,
                        polygon=polygon,
                    )

                    batch_detections.append(detection)
                    logger.info(
                        f"Detected plate: {plate.rec_text} "
                        f"(confidence: {plate.rec_confidence:.2f}, "
                        f"frame: {frame_number})"
                    )

            self.detections.extend(batch_detections)
            self.total_frames_processed += len(self.frame_buffer)

        except Exception as e:
            logger.error(f"Error during inference: {e}")

        finally:
            # Clear buffers
            self.frame_buffer.clear()
            self.frame_numbers.clear()

        return batch_detections

    def save_results(self, video_filename: str):
        """Save detection results to JSON file."""
        if not self.config.enabled or not self.storage_config.save_inference_results:
            return

        if not self.detections:
            logger.debug(f"No detections to save for {video_filename}")
            return

        # Create results filename
        video_stem = Path(video_filename).stem
        results_filename = f"{video_stem}_detections.json"
        results_path = self.storage_config.recording_dir / results_filename

        try:
            # Prepare results data
            results_data = {
                "video_file": video_filename,
                "total_detections": len(self.detections),
                "total_frames_processed": self.total_frames_processed,
                "detections": [det.to_dict() for det in self.detections],
            }

            # Write to file
            with open(results_path, "w") as f:
                json.dump(results_data, f, indent=2)

            logger.info(
                f"Saved {len(self.detections)} detections to {results_path.name}"
            )

            # Clear detections for next segment
            self.detections.clear()
            self.total_frames_processed = 0

        except Exception as e:
            logger.error(f"Failed to save detection results: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get inference statistics."""
        return {
            "total_detections": len(self.detections),
            "total_frames_processed": self.total_frames_processed,
            "frames_in_buffer": len(self.frame_buffer),
            "unique_plates": len(set(d.plate_text for d in self.detections)),
        }

    async def shutdown(self):
        """Cleanup resources."""
        logger.info("Shutting down inference processor")
        self.frame_buffer.clear()
        self.frame_numbers.clear()
        self.model = None
