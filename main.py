"""
pyinstaller main.py --onefile --windowed --name="Video Downloader" --icon="icon.png"
"""
import sys
from PySide6.QtWidgets import QApplication
from ui import DownloaderApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DownloaderApp()
    win.show()
    sys.exit(app.exec())
