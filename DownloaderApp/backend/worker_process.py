"""Code that runs inside a child process spawned by DownloadManager.

Deliberately depends only on the standard library and yt_dlp -- never on
PySide6 -- so the child process stays lightweight and a Qt/GUI crash can
never originate here. Both entry points are plain top-level functions
because multiprocessing's "spawn" start method (used on Windows and by
default on macOS) re-imports this module by name in the child and needs a
picklable, importable target.
"""
import os
import re

import yt_dlp
from yt_dlp.utils import DownloadCancelled

from . import utils

_SIGNIN_RE = re.compile(r"\b[Ss]ign in\b|--username")


class _RetryDownload(BaseException):
    """Raised to unwind out of a failed attempt and retry with credentials.

    Subclasses BaseException (not Exception) so yt-dlp's own error handling,
    which only catches Exception, can't swallow it.
    """


class _AuthInterceptingLogger:
    """yt-dlp logger that detects "sign in" / "video password required"
    messages and redirects them to the GUI via the event/command queues,
    blocking this (child) process until the user answers.
    """

    def __init__(self, cmd_queue, event_queue, cancel_event):
        self._cmd_queue = cmd_queue
        self._event_queue = event_queue
        self._cancel_event = cancel_event
        self._auth_attempted = False
        self.username = None
        self.password = None
        self.videopassword = None

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        if self._cancel_event.is_set():
            raise DownloadCancelled("Cancelled by user")
        if self._auth_attempted:
            return
        if _SIGNIN_RE.search(msg):
            self._auth_attempted = True
            self._event_queue.put(("login_request", None))
            kind, payload = self._cmd_queue.get()
            if kind == "login" and payload and (payload[0] or payload[1]):
                self.username, self.password = payload
                raise _RetryDownload("credentials supplied")
        elif "--video-password" in msg:
            self._auth_attempted = True
            self._event_queue.put(("password_request", None))
            kind, payload = self._cmd_queue.get()
            if kind == "password" and payload:
                self.videopassword = payload
                raise _RetryDownload("credentials supplied")


def run_fetch(cmd_queue, event_queue, url):
    try:
        with yt_dlp.YoutubeDL({
            "socket_timeout": 30,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
        }) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        event_queue.put(("error", str(e)))
        return

    is_playlist = info.get("_type") == "playlist" or "entries" in info
    entries = info.get("entries")
    if entries is not None:
        playlist_count = len(list(entries))
    else:
        playlist_count = info.get("playlist_count")

    # Only meaningful for a single video -- playlist entries can vary in
    # resolution, and extract_flat doesn't resolve their formats anyway.
    max_height = None
    if not is_playlist:
        heights = [f.get("height") for f in (info.get("formats") or []) if f.get("height")]
        if heights:
            max_height = max(heights)

    event_queue.put(("fetch_result", {
        "title": info.get("title") or info.get("id") or url,
        "thumbnail": info.get("thumbnail"),
        "is_playlist": is_playlist,
        "playlist_count": playlist_count,
        "max_height": max_height,
    }))


def run_download(cmd_queue, event_queue, cancel_event, params):
    ffmpeg_loc = utils.ffmpeg_location()
    if not ffmpeg_loc:
        event_queue.put(("error", utils.ffmpeg_missing_message()))
        return

    mode = params["mode"]
    is_playlist = params.get("is_playlist", False)
    download_all = params.get("download_playlist", True)
    output_dir = params["output_dir"]
    file_name = params.get("file_name") or "%(title)s"
    convert_to = params.get("convert_to", "original")

    if is_playlist and download_all:
        outtmpl = os.path.join(output_dir, f"{file_name} - %(playlist_index)s.%(ext)s")
    else:
        outtmpl = os.path.join(output_dir, f"{file_name}.%(ext)s")

    def on_progress(d):
        if cancel_event.is_set():
            raise DownloadCancelled("Cancelled by user")
        status = d.get("status")
        if status not in ("downloading", "finished"):
            return
        info = d.get("info_dict") or {}
        event_queue.put(("progress", {
            "status": status,
            "downloaded_bytes": d.get("downloaded_bytes"),
            "total_bytes": d.get("total_bytes") or d.get("total_bytes_estimate"),
            "speed": d.get("speed"),
            "eta": d.get("eta"),
            "playlist_index": info.get("playlist_index"),
            "n_entries": info.get("n_entries"),
        }))

    def on_pp(d):
        if cancel_event.is_set():
            raise DownloadCancelled("Cancelled by user")
        if d.get("status") in ("started", "processing"):
            event_queue.put(("stage", "converting"))

    logger = _AuthInterceptingLogger(cmd_queue, event_queue, cancel_event)

    while True:
        ydl_opts = {
            "outtmpl": outtmpl,
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "ffmpeg_location": ffmpeg_loc,
            "progress_hooks": [on_progress],
            "postprocessor_hooks": [on_pp],
            "logger": logger,
            "noplaylist": not (is_playlist and download_all),
        }
        if mode == "audio":
            ydl_opts["format"] = "bestaudio/best"
        else:
            height = params.get("resolution", utils.MAX_RESOLUTION)
            ydl_opts["format_sort"] = [f"res~{height}"]
        if convert_to != "original":
            if mode == "audio":
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": convert_to,
                }]
            else:
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": convert_to,
                }]
        if logger.username or logger.password:
            ydl_opts["username"] = logger.username
            ydl_opts["password"] = logger.password
        if logger.videopassword:
            ydl_opts["videopassword"] = logger.videopassword

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([params["url"]])
        except _RetryDownload:
            continue
        except DownloadCancelled:
            event_queue.put(("cancelled", None))
            return
        except Exception as e:
            event_queue.put(("error", str(e)))
            return
        else:
            event_queue.put(("finished", output_dir))
            return
