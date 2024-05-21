from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QProgressBar,
)
from threads import FetchFormatsThread, DownloadThread


class DownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("YouTube Downloader")
        self.setGeometry(100, 100, 400, 500)

        layout = QVBoxLayout()

        # URL input
        url_layout = QHBoxLayout()
        url_label = QLabel("YouTube URL:", self)
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("Enter YouTube URL here")
        self.fetch_button = QPushButton("Fetch", self)
        self.fetch_button.clicked.connect(self.fetch_formats)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_button)
        layout.addLayout(url_layout)

        # File name input
        file_name_layout = QHBoxLayout()
        file_name_label = QLabel("File Name:", self)
        self.file_name_input = QLineEdit(self)
        self.file_name_input.setPlaceholderText("(optional)")
        file_name_layout.addWidget(file_name_label)
        file_name_layout.addWidget(self.file_name_input)
        layout.addLayout(file_name_layout)

        # Download type
        type_layout = QHBoxLayout()
        type_label = QLabel("Download Type:", self)
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["video", "audio"])
        self.type_combo.currentIndexChanged.connect(self.download_type_changed)
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # Video quality
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Video Quality:", self)
        self.quality_combo = QComboBox(self)
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        layout.addLayout(quality_layout)

        # Video format
        video_format_layout = QHBoxLayout()
        video_format_label = QLabel("Video Format:", self)
        self.video_format_combo = QComboBox(self)
        self.video_format_combo.addItems(["mp4", "mkv", "webm", "flv"])
        video_format_layout.addWidget(video_format_label)
        video_format_layout.addWidget(self.video_format_combo)
        layout.addLayout(video_format_layout)

        # Audio format
        audio_format_layout = QHBoxLayout()
        audio_format_label = QLabel("Audio Format:", self)
        self.audio_format_combo = QComboBox(self)
        self.audio_format_combo.addItems(["mp3", "m4a", "wav", "aac", "flac"])
        self.audio_format_combo.setEnabled(False)
        audio_format_layout.addWidget(audio_format_label)
        audio_format_layout.addWidget(self.audio_format_combo)
        layout.addLayout(audio_format_layout)

        # Output path
        output_layout = QHBoxLayout()
        output_label = QLabel("Output Path:", self)
        self.output_input = QLineEdit(self)
        self.output_input.setPlaceholderText("Select or enter output directory")
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_output_path)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_input)
        output_layout.addWidget(self.browse_button)
        layout.addLayout(output_layout)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Download and Cancel buttons
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("Download", self)
        self.download_button.clicked.connect(self.download)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.cancel_download)
        self.clear_button = QPushButton("Clear", self)
        self.clear_button.clicked.connect(self.clear_fields)
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.clear_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setStyleSheet(self.dark_mode_stylesheet())

        self.thread: DownloadThread = None

    def fetch_formats(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a YouTube URL.")
            return

        self.quality_combo.clear()
        self.fetch_thread = FetchFormatsThread(url)
        self.fetch_thread.finished.connect(self.populate_formats)
        self.fetch_thread.error.connect(self.show_error)
        self.fetch_thread.start()

    def populate_formats(self, formats):
        self.quality_combo.addItems(formats)

    def show_error(self, error):
        QMessageBox.critical(self, "Error", error)

    def clear_fields(self):
        self.url_input.clear()
        self.file_name_input.clear()
        self.quality_combo.clear()
        self.output_input.clear()
        self.progress_bar.setValue(0)

    def browse_output_path(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_input.setText(directory)

    def download_type_changed(self):
        if self.type_combo.currentText() == "audio":
            self.quality_combo.setDisabled(True)
            self.audio_format_combo.setEnabled(True)
            self.video_format_combo.setDisabled(True)
        else:
            self.quality_combo.setDisabled(False)
            self.audio_format_combo.setEnabled(False)
            self.video_format_combo.setDisabled(False)

    def download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a YouTube URL.")
            return

        file_name = self.file_name_input.text().strip()
        if not file_name:
            file_name = (
                "%(title)s"  # Default to video title if no file name is provided
            )

        output_path = self.output_input.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Input Error", "Please select an output path.")
            return
        self.progress_bar.setValue(0)

        download_type = self.type_combo.currentText()
        video_quality = (
            self.quality_combo.currentText() if download_type == "video" else None
        )
        audio_format = (
            self.audio_format_combo.currentText() if download_type == "audio" else None
        )
        video_format = (
            self.video_format_combo.currentText() if download_type == "video" else None
        )
        ffmpeg_location = "/opt/homebrew/bin/ffmpeg"  # Update this path if necessary

        self.thread = DownloadThread(
            url,
            download_type,
            video_quality,
            output_path,
            file_name,
            audio_format,
            video_format,
            ffmpeg_location,
        )
        self.thread.progress.connect(self.update_progress)
        self.thread.message.connect(self.show_message)
        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def show_message(self, message):
        QMessageBox.information(self, "Download Status", message)

    def cancel_download(self):
        if self.thread is not None:
            self.thread.cancel_download()

    def dark_mode_stylesheet(self):
        return """
        QWidget {
            background-color: #2E2E2E;
            color: #F0F0F0;
        }
        QPushButton {
            background-color: #4B4B4B;
            border: 1px solid #555555;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #555555;
        }
        QLineEdit, QComboBox, QProgressBar {
            background-color: #3E3E3E;
            border: 1px solid #555555;
            padding: 3px;
            border-radius: 3px;
        }
        QProgressBar::chunk {
            background-color: #2196F3;
        }
        QLabel {
            font-size: 14px;
        }
        """
