"""
pyinstaller main.py --onefile --windowed --name="Video Downloader" --icon="./DownloaderApp/resources/icon.png"
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from DownloaderApp import DownloaderApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("./DownloaderApp/resources/icon.png"))
    win = DownloaderApp()
    win.show()
    sys.exit(app.exec())
