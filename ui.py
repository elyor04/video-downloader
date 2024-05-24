from PySide6.QtWidgets import (
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
        self.setWindowTitle("Video Downloader")
        self.setGeometry(100, 100, 400, 500)

        layout = QVBoxLayout()

        # URL input
        url_layout = QHBoxLayout()
        url_label = QLabel("Video URL:", self)
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("Enter Video URL here")
        self.fetch_button = QPushButton("Fetch", self)
        self.fetch_button.clicked.connect(self.fetch_formats)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_button)
        layout.addLayout(url_layout)

        # Download type
        type_layout = QHBoxLayout()
        type_label = QLabel("Download Type:", self)
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["video", "audio"])
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # Desired format
        format_layout = QHBoxLayout()
        format_label = QLabel("Desired Format:", self)
        self.format_combo = QComboBox(self)
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        layout.addLayout(format_layout)

        # Convert to
        convert_to_layout = QHBoxLayout()
        convert_to_label = QLabel("Convert To:", self)
        self.convert_to_combo = QComboBox(self)
        self.convert_to_combo.addItems(
            ["original", "mp4", "mkv", "webm", "mp3", "m4a", "wav"]
        )
        convert_to_layout.addWidget(convert_to_label)
        convert_to_layout.addWidget(self.convert_to_combo)
        layout.addLayout(convert_to_layout)

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

        # File name input
        file_name_layout = QHBoxLayout()
        file_name_label = QLabel("File Name:", self)
        self.file_name_input = QLineEdit(self)
        self.file_name_input.setPlaceholderText("(optional)")
        file_name_layout.addWidget(file_name_label)
        file_name_layout.addWidget(self.file_name_input)
        layout.addLayout(file_name_layout)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Download, Cancel, and Clear buttons
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

        self.download_thread: DownloadThread = None
        self.available_formats: dict = None

    def fetch_formats(self):
        url = self.url_input.text().strip()
        if not url:
            return QMessageBox.warning(self, "Error", "Please enter a Video URL.")
        download_type = self.type_combo.currentText()

        self.format_combo.clear()
        self.fetch_thread = FetchFormatsThread(url, download_type)
        self.fetch_thread.finished.connect(self.populate_formats)
        self.fetch_thread.message.connect(self.show_message)
        self.fetch_thread.start()

    def populate_formats(self, formats):
        self.available_formats = formats
        download_type = self.type_combo.currentText()
        self.format_combo.addItems(formats[download_type])

    def show_message(self, message):
        QMessageBox.information(self, None, message)

    def browse_output_path(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_input.setText(directory)

    def download(self):
        url = self.url_input.text().strip()
        if not url:
            return QMessageBox.warning(self, "Error", "Please enter a Video URL.")

        file_name = self.file_name_input.text().strip()
        if not file_name:
            file_name = (
                "%(title)s"  # Default to video title if no file name is provided
            )

        output_path = self.output_input.text().strip()
        if not output_path:
            return QMessageBox.warning(self, "Error", "Please select an output path.")

        download_type = self.type_combo.currentText()
        desired_format = self.format_combo.currentText()
        convert_to = self.convert_to_combo.currentText()
        ffmpeg_location = (
            "/opt/homebrew/bin/ffmpeg"  # Update this path if you are not using MacOS
        )

        if desired_format == "":
            return QMessageBox.warning(
                self, "Error", "Please fetch and select desired format."
            )
        self.progress_bar.setValue(0)

        self.download_thread = DownloadThread(
            url,
            download_type,
            desired_format,
            self.available_formats,
            output_path,
            file_name,
            convert_to,
            ffmpeg_location,
        )
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.message.connect(self.show_message)
        self.download_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def cancel_download(self):
        if self.download_thread is not None:
            self.download_thread.cancel_download()

    def clear_fields(self):
        self.url_input.clear()
        self.file_name_input.clear()
        self.format_combo.clear()
        self.output_input.clear()
        self.progress_bar.setValue(0)

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
