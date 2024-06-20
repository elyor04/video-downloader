import os
import re
import shutil
import platform
from PySide6.QtCore import QThread, Signal
import yt_dlp


class FetchFormatsThread(QThread):
    finished = Signal(dict)
    message = Signal(str)

    def __init__(self, url, download_type):
        super().__init__()
        self.url = url
        self.download_type = download_type

    def run(self):
        try:
            with yt_dlp.YoutubeDL() as ydl:
                info = ydl.extract_info(self.url, download=False)
                formats = {"video": [], "audio": []}

                for f in info.get("formats", []):
                    if f["audio_ext"] != "none":
                        formats["audio"].append(f["ext"])
                    elif f["video_ext"] != "none":
                        formats["video"].append((f["height"], f["ext"]))

                formats["audio"] = sorted(set(formats["audio"]), reverse=True)
                formats["video"] = [
                    f"{f[0]}p {f[1]}"
                    for f in sorted(set(formats["video"]), reverse=True)
                ]

                if not formats[self.download_type]:
                    return self.message.emit("No format found.")
                self.finished.emit(formats)

        except Exception as e:
            self.message.emit(f"Error occurred: {e}")


class DownloadThread(QThread):
    progress = Signal(int)
    message = Signal(str)

    def __init__(
        self,
        url,
        download_type,
        video_format,
        available_formats,
        output_path,
        file_name,
        convert_to,
    ):
        super().__init__()
        self.url = url
        self.download_type = download_type
        self.video_format = video_format
        self.available_formats = available_formats
        self.output_path = output_path
        self.file_name = file_name
        self.convert_to = convert_to
        self.is_canceled = False

    def run(self):
        # ffmpeg_location = "/opt/homebrew/bin/ffmpeg"
        ffmpeg_location = self._ffmpeg_location()
        if not ffmpeg_location:
            return

        ydl_opts = {
            "format": self._format(),
            "outtmpl": self._outtmpl(),
            "progress_hooks": [self._progress_hook],
            "ffmpeg_location": ffmpeg_location,
        }

        if self.convert_to != "original":
            ydl_opts["postprocessors"] = [self._postprocessor()]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.progress.emit(100)
            self.message.emit("Download completed successfully.")

        except Exception as e:
            self.message.emit(f"Error occurred: {e}")

    def _ffmpeg_location(self):
        ffmpeg_location = shutil.which("ffmpeg")

        if not ffmpeg_location:
            system = platform.system()
            message = "Error: FFmpeg is not installed. "

            if system == "Windows":
                message += "Please run this command: winget install ffmpeg"
            elif system == "Darwin":
                message += "Please run this command: brew install ffmpeg"
            elif system == "Linux":
                message += "Please run this command: sudo apt install ffmpeg"
            else:
                message += "Please refer to this link: https://ffmpeg.org/download.html"

            self.message.emit(message)
        return ffmpeg_location

    def _format(self):
        if self.download_type == "audio":
            return f"bestaudio[ext={self.video_format}]"

        q, f = self.video_format.split()
        if not self.available_formats["audio"]:
            return f"best[height={q[:-1]}][ext={f}]"

        if f in self.available_formats["audio"]:
            audio = f
        elif "m4a" in self.available_formats["audio"]:
            audio = "m4a"
        else:
            audio = None

        if not audio:
            return f"bestvideo[height={q[:-1]}][ext={f}]+bestaudio"
        return f"bestvideo[height={q[:-1]}][ext={f}]+bestaudio[ext={audio}]/best"

    def _outtmpl(self):
        if self.download_type == "audio":
            return os.path.join(self.output_path, f"{self.file_name}.%(ext)s")
        q, f = self.video_format.split()
        return os.path.join(self.output_path, f"{self.file_name} ({q}).%(ext)s")

    def _postprocessor(self):
        if self.download_type == "audio":
            return {
                "key": "FFmpegExtractAudio",
                "preferredcodec": self.convert_to,
            }
        return {
            "key": "FFmpegVideoConvertor",
            "preferedformat": self.convert_to,
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
