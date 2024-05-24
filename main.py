"""
pyinstaller main.py --onefile --windowed --name="Video Downloader" --icon="icon.png"
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui import DownloaderApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.png"))
    win = DownloaderApp()
    win.show()
    sys.exit(app.exec())
