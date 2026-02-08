import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class CompressionConfig:
    """Video compression configuration"""
    enabled: bool = True
    codec: str = "libx265"  # H.265 codec
    crf: int = 28  # Constant Rate Factor (18-28 good quality, higher = smaller)
    preset: str = "medium"  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
    max_resolution: Optional[str] = None  # e.g., "1920x1080", None for original
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"


@dataclass
class BatchConfig:
    """Video batching configuration"""
    enabled: bool = True
    window_hours: int = 4  # Combine videos from this time window
    min_files: int = 1  # Minimum files to create a batch
    max_batch_size_mb: int = 5000  # Maximum batch size in MB


@dataclass
class ScheduleConfig:
    """Upload scheduling configuration"""
    upload_interval_hours: int = 6  # Upload every 6 hours
    retry_delays_minutes: list[int] = field(default_factory=lambda: [1, 5, 30, 120])  # Exponential backoff
    max_retries: int = 4
    check_network: bool = True  # Check network availability before upload
    min_bandwidth_mbps: float = 1.0  # Minimum bandwidth to proceed with upload


@dataclass
class StorageConfig:
    """Local storage configuration"""
    buffer_dir: str = "/tmp/ooda_video_buffer"
    max_buffer_size_gb: int = 20
    emergency_upload_threshold: float = 0.8  # Trigger upload at 80% full
    cleanup_after_upload: bool = True
    keep_originals: bool = False  # Keep original files after compression


@dataclass
class S3Config:
    """S3 upload configuration"""
    bucket_name: str = ""
    region: str = "us-east-1"
    storage_class: str = "INTELLIGENT_TIERING"  # STANDARD, INTELLIGENT_TIERING, STANDARD_IA
    multipart_threshold_mb: int = 100
    multipart_chunksize_mb: int = 10
    use_acceleration: bool = False
    key_prefix: str = "video_chunks"


@dataclass
class MonitoringConfig:
    """Monitoring and logging configuration"""
    log_level: str = "INFO"
    log_file: Optional[str] = "/var/log/ooda/upload.log"
    enable_cloudwatch: bool = False
    cloudwatch_namespace: str = "OODA/Upload"
    track_costs: bool = True


@dataclass
class UploadConfig:
    """Main upload configuration combining all sub-configs"""
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    batching: BatchConfig = field(default_factory=BatchConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    s3: S3Config = field(default_factory=S3Config)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'UploadConfig':
        """Create config from dictionary"""
        return cls(
            compression=CompressionConfig(**config_dict.get('compression', {})),
            batching=BatchConfig(**config_dict.get('batching', {})),
            schedule=ScheduleConfig(**config_dict.get('schedule', {})),
            storage=StorageConfig(**config_dict.get('storage', {})),
            s3=S3Config(**config_dict.get('s3', {})),
            monitoring=MonitoringConfig(**config_dict.get('monitoring', {}))
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'UploadConfig':
        """Load configuration from YAML file"""
        with open(yaml_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        return cls.from_dict(config_dict)

    @classmethod
    def from_json(cls, json_path: str) -> 'UploadConfig':
        """Load configuration from JSON file"""
        with open(json_path, 'r') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)

    @classmethod
    def from_env(cls) -> 'UploadConfig':
        """Load configuration from environment variables"""
        config = cls()

        # S3 configuration from environment
        if os.getenv('OODA_S3_BUCKET'):
            config.s3.bucket_name = os.getenv('OODA_S3_BUCKET')
        if os.getenv('OODA_S3_REGION'):
            config.s3.region = os.getenv('OODA_S3_REGION')
        if os.getenv('OODA_S3_STORAGE_CLASS'):
            config.s3.storage_class = os.getenv('OODA_S3_STORAGE_CLASS')

        # Storage configuration from environment
        if os.getenv('OODA_BUFFER_DIR'):
            config.storage.buffer_dir = os.getenv('OODA_BUFFER_DIR')
        if os.getenv('OODA_MAX_BUFFER_GB'):
            config.storage.max_buffer_size_gb = int(os.getenv('OODA_MAX_BUFFER_GB'))

        # Schedule configuration from environment
        if os.getenv('OODA_UPLOAD_INTERVAL_HOURS'):
            config.schedule.upload_interval_hours = int(os.getenv('OODA_UPLOAD_INTERVAL_HOURS'))

        # Compression configuration from environment
        if os.getenv('OODA_COMPRESSION_ENABLED'):
            config.compression.enabled = os.getenv('OODA_COMPRESSION_ENABLED').lower() == 'true'
        if os.getenv('OODA_COMPRESSION_CRF'):
            config.compression.crf = int(os.getenv('OODA_COMPRESSION_CRF'))

        # Monitoring configuration from environment
        if os.getenv('OODA_LOG_LEVEL'):
            config.monitoring.log_level = os.getenv('OODA_LOG_LEVEL')
        if os.getenv('OODA_LOG_FILE'):
            config.monitoring.log_file = os.getenv('OODA_LOG_FILE')

        return config

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'UploadConfig':
        """
        Load configuration with priority:
        1. Specified config file (if provided)
        2. Environment variables
        3. Default config file locations
        4. Default values
        """
        # Start with environment variables
        config = cls.from_env()

        # If config path is specified, use it
        if config_path:
            path = Path(config_path)
            if path.exists():
                if path.suffix in ['.yaml', '.yml']:
                    config = cls.from_yaml(config_path)
                elif path.suffix == '.json':
                    config = cls.from_json(config_path)
                else:
                    raise ValueError(f"Unsupported config file format: {path.suffix}")
            else:
                raise FileNotFoundError(f"Config file not found: {config_path}")
        else:
            # Look for default config files
            default_paths = [
                'upload_config.yaml',
                'upload_config.yml',
                'upload_config.json',
                '/etc/ooda/upload_config.yaml',
                str(Path.home() / '.ooda' / 'upload_config.yaml')
            ]

            for default_path in default_paths:
                path = Path(default_path)
                if path.exists():
                    if path.suffix in ['.yaml', '.yml']:
                        return cls.from_yaml(str(path))
                    elif path.suffix == '.json':
                        return cls.from_json(str(path))

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            'compression': asdict(self.compression),
            'batching': asdict(self.batching),
            'schedule': asdict(self.schedule),
            'storage': asdict(self.storage),
            's3': asdict(self.s3),
            'monitoring': asdict(self.monitoring)
        }

    def save_yaml(self, path: str):
        """Save configuration to YAML file"""
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    def save_json(self, path: str):
        """Save configuration to JSON file"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
