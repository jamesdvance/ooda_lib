import hashlib
import subprocess
import json
import shutil
import psutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from .models import VideoMetadata


def calculate_checksum(file_path: str, algorithm: str = "sha256") -> str:
    """
    Calculate checksum of a file

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha1, sha256)

    Returns:
        Hexadecimal hash string
    """
    hash_func = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b''):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def get_video_metadata(file_path: str) -> VideoMetadata:
    """
    Extract metadata from video file using ffprobe

    Args:
        file_path: Path to video file

    Returns:
        VideoMetadata object
    """
    path = Path(file_path)

    # Get file size and checksum
    file_size = path.stat().st_size
    created_at = datetime.fromtimestamp(path.stat().st_ctime)

    # Calculate checksum (do this first while we have the file)
    checksum = calculate_checksum(file_path)

    # Try to get video metadata using ffprobe
    duration = None
    width = None
    height = None
    codec = None
    fps = None
    bitrate = None

    try:
        # Check if ffprobe is available
        if shutil.which('ffprobe'):
            result = subprocess.run([
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)

                # Extract format info
                if 'format' in data:
                    duration = float(data['format'].get('duration', 0))
                    bitrate = int(data['format'].get('bit_rate', 0))

                # Extract video stream info
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width')
                        height = stream.get('height')
                        codec = stream.get('codec_name')

                        # Calculate FPS from frame rate
                        fps_str = stream.get('r_frame_rate', '0/1')
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            if int(den) > 0:
                                fps = int(num) / int(den)
                        break
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, Exception):
        # If ffprobe fails, we'll just use basic metadata
        pass

    return VideoMetadata(
        file_path=file_path,
        file_size=file_size,
        checksum=checksum,
        created_at=created_at,
        duration=duration,
        width=width,
        height=height,
        codec=codec,
        fps=fps,
        bitrate=bitrate
    )


def get_disk_usage(path: str) -> Dict[str, Any]:
    """
    Get disk usage statistics for a path

    Args:
        path: Directory path to check

    Returns:
        Dictionary with usage statistics
    """
    path_obj = Path(path)

    if not path_obj.exists():
        path_obj.mkdir(parents=True, exist_ok=True)

    # Get disk usage
    usage = shutil.disk_usage(path)

    # Calculate directory size if it exists
    dir_size = 0
    if path_obj.is_dir():
        dir_size = sum(f.stat().st_size for f in path_obj.rglob('*') if f.is_file())

    return {
        'total_bytes': usage.total,
        'used_bytes': usage.used,
        'free_bytes': usage.free,
        'total_gb': usage.total / (1024**3),
        'used_gb': usage.used / (1024**3),
        'free_gb': usage.free / (1024**3),
        'percent_used': (usage.used / usage.total) * 100,
        'directory_size_bytes': dir_size,
        'directory_size_gb': dir_size / (1024**3)
    }


def get_network_speed() -> Optional[float]:
    """
    Estimate current network upload speed in Mbps
    This is a simple implementation that checks network stats

    Returns:
        Estimated upload speed in Mbps, or None if cannot determine
    """
    try:
        # Get network I/O counters
        net_before = psutil.net_io_counters()
        import time
        time.sleep(1)
        net_after = psutil.net_io_counters()

        # Calculate bytes sent in 1 second
        bytes_sent = net_after.bytes_sent - net_before.bytes_sent

        # Convert to Mbps
        mbps = (bytes_sent * 8) / (1024 * 1024)

        return mbps
    except Exception:
        return None


def check_network_available(min_speed_mbps: float = 1.0) -> bool:
    """
    Check if network is available and has minimum speed

    Args:
        min_speed_mbps: Minimum required speed in Mbps

    Returns:
        True if network is available and fast enough
    """
    try:
        # Check if any network interface is up
        net_stats = psutil.net_if_stats()
        has_connection = any(stat.isup for stat in net_stats.values())

        if not has_connection:
            return False

        # If we have connection, check speed
        speed = get_network_speed()
        if speed is None:
            # If we can't measure speed but have connection, assume it's ok
            return True

        return speed >= min_speed_mbps
    except Exception:
        # If we can't check, assume network is available
        return True


def format_bytes(bytes: int) -> str:
    """
    Format bytes to human-readable string

    Args:
        bytes: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1h 23m 45s")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or len(parts) == 0:
        parts.append(f"{secs}s")

    return " ".join(parts)


def ensure_dir_exists(path: str) -> Path:
    """
    Ensure directory exists, create if it doesn't

    Args:
        path: Directory path

    Returns:
        Path object
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def is_video_file(file_path: str) -> bool:
    """
    Check if file is a video based on extension

    Args:
        file_path: Path to file

    Returns:
        True if file appears to be a video
    """
    video_extensions = {
        '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv',
        '.m4v', '.mpg', '.mpeg', '.3gp', '.webm', '.ts'
    }

    return Path(file_path).suffix.lower() in video_extensions


def generate_s3_key(file_path: str, prefix: str = "video_chunks") -> str:
    """
    Generate S3 key from file path with timestamp organization

    Args:
        file_path: Local file path
        prefix: S3 key prefix

    Returns:
        S3 key string
    """
    path = Path(file_path)
    now = datetime.utcnow()

    # Organize by year/month/day for easier management
    date_prefix = now.strftime("%Y/%m/%d")

    # Include timestamp in filename to avoid collisions
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{path.name}"

    return f"{prefix}/{date_prefix}/{filename}"


def cleanup_old_files(directory: str, max_age_hours: int = 24) -> int:
    """
    Clean up old files in directory

    Args:
        directory: Directory to clean
        max_age_hours: Maximum age of files to keep

    Returns:
        Number of files deleted
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return 0

    now = datetime.utcnow()
    deleted = 0

    for file_path in dir_path.rglob('*'):
        if file_path.is_file():
            # Get file modification time
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            age_hours = (now - mtime).total_seconds() / 3600

            if age_hours > max_age_hours:
                try:
                    file_path.unlink()
                    deleted += 1
                except Exception:
                    pass

    return deleted


def safe_delete_file(file_path: str) -> bool:
    """
    Safely delete a file

    Args:
        file_path: Path to file to delete

    Returns:
        True if deleted successfully
    """
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False
    except Exception:
        return False


def get_file_age_hours(file_path: str) -> float:
    """
    Get age of file in hours

    Args:
        file_path: Path to file

    Returns:
        Age in hours
    """
    path = Path(file_path)
    if not path.exists():
        return 0.0

    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    age = datetime.utcnow() - mtime
    return age.total_seconds() / 3600
