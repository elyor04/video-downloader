import os
import re
from PyQt6.QtCore import QThread, pyqtSignal
import yt_dlp


class FetchFormatsThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            with yt_dlp.YoutubeDL() as ydl:
                info = ydl.extract_info(self.url, download=False)
                formats = [
                    format["height"]
                    for format in info.get("formats", [])
                    if format["video_ext"] != "none"
                ]
                formats = [
                    f"{format}p" for format in sorted(set(formats), reverse=True)
                ]
                self.finished.emit(formats)
        except Exception as e:
            self.error.emit(str(e))


class DownloadThread(QThread):
    progress = pyqtSignal(int)
    message = pyqtSignal(str)

    def __init__(
        self,
        url,
        download_type,
        video_quality,
        output_path,
        file_name,
        audio_format,
        video_format,
        ffmpeg_location=None,
    ):
        super().__init__()
        self.url = url
        self.download_type = download_type
        self.video_quality = video_quality
        self.output_path = output_path
        self.file_name = file_name
        self.audio_format = audio_format
        self.video_format = video_format
        self.ffmpeg_location = ffmpeg_location
        self.is_canceled = False

    def run(self):
        ydl_opts = {
            "format": self._format(),
            "outtmpl": self._outtmpl(),
            "postprocessors": [self._postprocessor()],
            "progress_hooks": [self._progress_hook],
        }

        if self.ffmpeg_location:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_location

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.progress.emit(100)
            self.message.emit("Download completed successfully.")
        except Exception as e:
            self.message.emit(f"An error occurred: {e}")

    def _format(self):
        if self.download_type == "audio":
            return "bestaudio"
        return f"bestvideo[height={self.video_quality[:-1]}]+bestaudio"

    def _outtmpl(self):
        if self.download_type == "audio":
            return os.path.join(self.output_path, f"{self.file_name}.%(ext)s")
        return os.path.join(
            self.output_path, f"{self.file_name} ({self.video_quality}).%(ext)s"
        )

    def _postprocessor(self):
        if self.download_type == "audio":
            return {
                "key": "FFmpegExtractAudio",
                "preferredcodec": self.audio_format,
            }
        return {
            "key": "FFmpegVideoConvertor",
            "preferedformat": self.video_format,
        }

    def _progress_hook(self, d):
        if self.is_canceled:
            raise yt_dlp.DownloadError("Download canceled by user")

        if d["status"] == "downloading":
            percent_str = d["_percent_str"]
            percent_clean = re.search(r"\d+\.\d+", percent_str).group()
            self.progress.emit(int(float(percent_clean)))
        elif d["status"] == "finished":
            self.progress.emit(99)

    def cancel_download(self):
        self.is_canceled = True
