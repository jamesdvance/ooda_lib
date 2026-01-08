"""
OODA Edge Inference Module

Video capture, recording, and license plate recognition pipeline.
"""
from .config import Config, VideoConfig, InferenceConfig, StorageConfig
from .recorder import VideoRecorder
from .processor import InferenceProcessor, Detection
from .storage import StorageManager

__version__ = "0.1.0"

__all__ = [
    "Config",
    "VideoConfig",
    "InferenceConfig",
    "StorageConfig",
    "VideoRecorder",
    "InferenceProcessor",
    "Detection",
    "StorageManager",
]
