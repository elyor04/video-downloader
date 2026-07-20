from typing import Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from . import utils
from .job import ACTIVE_STATES, TERMINAL_STATES, DownloadJob


class DownloadQueueModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    UrlRole = Qt.UserRole + 2
    TitleRole = Qt.UserRole + 3
    ThumbnailRole = Qt.UserRole + 4
    StateRole = Qt.UserRole + 5
    StageRole = Qt.UserRole + 6
    ModeRole = Qt.UserRole + 7
    ProgressRole = Qt.UserRole + 8
    PlaylistIndexRole = Qt.UserRole + 9
    PlaylistCountRole = Qt.UserRole + 10
    DownloadedTextRole = Qt.UserRole + 11
    TotalTextRole = Qt.UserRole + 12
    SpeedTextRole = Qt.UserRole + 13
    EtaTextRole = Qt.UserRole + 14
    ErrorMessageRole = Qt.UserRole + 15
    CanCancelRole = Qt.UserRole + 16
    CanRemoveRole = Qt.UserRole + 17
    CanOpenFolderRole = Qt.UserRole + 18

    _ROLE_NAMES = {
        IdRole: b"jobId",
        UrlRole: b"url",
        TitleRole: b"title",
        ThumbnailRole: b"thumbnail",
        StateRole: b"jobState",
        StageRole: b"stage",
        ModeRole: b"mode",
        ProgressRole: b"progress",
        PlaylistIndexRole: b"playlistIndex",
        PlaylistCountRole: b"playlistCount",
        DownloadedTextRole: b"downloadedText",
        TotalTextRole: b"totalText",
        SpeedTextRole: b"speedText",
        EtaTextRole: b"etaText",
        ErrorMessageRole: b"errorMessage",
        CanCancelRole: b"canCancel",
        CanRemoveRole: b"canRemove",
        CanOpenFolderRole: b"canOpenFolder",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: list[DownloadJob] = []

    def roleNames(self):
        return dict(self._ROLE_NAMES)

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._jobs)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self._jobs)):
            return None
        job = self._jobs[index.row()]
        if role == self.IdRole:
            return job.id
        if role == self.UrlRole:
            return job.url
        if role == self.TitleRole:
            return job.title or job.url
        if role == self.ThumbnailRole:
            return job.thumbnail
        if role == self.StateRole:
            return job.state
        if role == self.StageRole:
            return job.stage
        if role == self.ModeRole:
            return job.mode
        if role == self.ProgressRole:
            return job.progress
        if role == self.PlaylistIndexRole:
            return (job.playlist_index or 0) + 1 if job.playlist_index is not None else 0
        if role == self.PlaylistCountRole:
            return job.playlist_count or 0
        if role == self.DownloadedTextRole:
            return utils.format_bytes(job.downloaded_bytes)
        if role == self.TotalTextRole:
            return utils.format_bytes(job.total_bytes)
        if role == self.SpeedTextRole:
            return utils.format_speed(job.speed)
        if role == self.EtaTextRole:
            return utils.format_eta(job.eta)
        if role == self.ErrorMessageRole:
            return job.error_message
        if role == self.CanCancelRole:
            return job.state in ACTIVE_STATES
        if role == self.CanRemoveRole:
            return job.state in TERMINAL_STATES
        if role == self.CanOpenFolderRole:
            return job.state == "success"
        return None

    # -- mutation API used by DownloadManager (not QML-facing) --

    def add_job(self, job: DownloadJob) -> None:
        row = len(self._jobs)
        self.beginInsertRows(QModelIndex(), row, row)
        self._jobs.append(job)
        self.endInsertRows()

    def job_by_id(self, job_id: str) -> Optional[DownloadJob]:
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None

    def index_of(self, job_id: str) -> int:
        for i, job in enumerate(self._jobs):
            if job.id == job_id:
                return i
        return -1

    def notify_row_changed(self, job_id: str) -> None:
        row = self.index_of(job_id)
        if row < 0:
            return
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)

    def remove_job(self, job_id: str) -> None:
        row = self.index_of(job_id)
        if row < 0:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._jobs[row]
        self.endRemoveRows()

    def jobs(self) -> list[DownloadJob]:
        return list(self._jobs)
