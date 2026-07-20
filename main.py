"""
pyinstaller main.py --onefile --windowed --name="Video Downloader" ^
    --icon="DownloaderApp/resources/icon.png" ^
    --add-data "DownloaderApp/qml;DownloaderApp/qml" ^
    --add-data "DownloaderApp/resources;DownloaderApp/resources" ^
    --add-data "DownloaderApp/i18n;DownloaderApp/i18n"
"""
import multiprocessing
import sys

from PySide6.QtCore import QTranslator
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from DownloaderApp.backend.download_manager import DownloadManager
from DownloaderApp.backend.utils import resource_path


def main():
    QQuickStyle.setStyle("Material")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Video Downloader")
    app.setOrganizationName("elyor04")
    app.setWindowIcon(QIcon(str(resource_path("resources/icon.png"))))

    translator = QTranslator()
    engine = QQmlApplicationEngine()

    manager = DownloadManager(engine, translator)
    engine.rootContext().setContextProperty("backend", manager)
    app.aboutToQuit.connect(manager.requestShutdown)

    engine.load(str(resource_path("qml/Main.qml")))
    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
