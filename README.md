# Video Downloader

Download videos and audio from YouTube, Instagram, TikTok, and other sites — with a queue for multiple downloads at once, resolution and format selection, and a modern QML interface.

## Features

- Paste a URL and it's automatically previewed (title and thumbnail) before you add it — no separate "Fetch" step; the Download button enables once the preview succeeds, and any failure (bad link, network issue, site blocking the request) shows up as a clear error dialog
- Add several URLs and download up to 2 at a time; the rest wait in a queue and start automatically
- Video or audio mode, resolution selection (narrowed to what's actually available once a video is previewed), optional format conversion (mp4/mkv/webm/mp3/m4a/wav)
- Playlist detection with a confirmation prompt before downloading an entire playlist
- Sign-in / video-password support for gated content
- Each download runs in its own isolated background process, so a failure in one never affects the app or other downloads, and cancelling is immediate
- Interface available in English, Russian, and Uzbek (switchable at any time, top-right)

## Installation

```
pip install -r requirements.txt
```

### FFmpeg (required for merging/converting)

- **Windows**: `winget install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

## Usage

```
python main.py
```
