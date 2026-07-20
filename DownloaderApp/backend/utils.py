import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_PACKAGE_DIR = Path(__file__).resolve().parent.parent  # .../DownloaderApp

MAX_RESOLUTION = 65535
RESOLUTION_LADDER: list[tuple[int, str]] = [
    (MAX_RESOLUTION, "Best"),
    (4320, "4320p (8K)"),
    (2160, "2160p (4K)"),
    (1440, "1440p"),
    (1080, "1080p"),
    (720, "720p"),
    (480, "480p"),
    (360, "360p"),
    (240, "240p"),
    (144, "144p"),
]
VIDEO_CONVERT_OPTIONS = ["original", "mp4", "mkv", "webm"]
AUDIO_CONVERT_OPTIONS = ["original", "mp3", "m4a", "wav"]
MAX_CONCURRENT_DOWNLOADS = 2


def resource_path(relative: str) -> Path:
    """Resolve a path under DownloaderApp/, both in dev and under PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "DownloaderApp"
    else:
        base = _PACKAGE_DIR
    return base / relative


def ffmpeg_location() -> Optional[str]:
    return shutil.which("ffmpeg")


def ffmpeg_missing_message() -> str:
    system = platform.system()
    message = "FFmpeg is not installed. "
    if system == "Windows":
        message += "Please run this command: winget install ffmpeg"
    elif system == "Darwin":
        message += "Please run this command: brew install ffmpeg"
    elif system == "Linux":
        message += "Please run this command: sudo apt install ffmpeg"
    else:
        message += "Please refer to this link: https://ffmpeg.org/download.html"
    return message


def open_in_file_manager(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def format_bytes(n: Optional[float]) -> str:
    if n is None or n < 0:
        return "?"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def format_speed(bytes_per_sec: Optional[float]) -> str:
    if bytes_per_sec is None or bytes_per_sec < 0:
        return "?"
    return f"{format_bytes(bytes_per_sec)}/s"


def format_eta(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "?"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def check_download_dir(path: str, create: bool = False) -> Optional[str]:
    """Return None if `path` is a writable directory, else a short reason."""
    if create:
        try:
            os.makedirs(path, exist_ok=True)
        except FileExistsError:
            return "Not a directory"
        except OSError:
            return "Permission denied"
    elif not os.path.isdir(path):
        return "Not a directory"
    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        return "Permission denied"
    return None
