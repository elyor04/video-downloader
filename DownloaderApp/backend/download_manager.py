import queue as _queue
import traceback
from multiprocessing import Event as MpEvent
from multiprocessing import Process, Queue
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QLocale,
    QObject,
    QSettings,
    Qt,
    QTimer,
    QUrl,
    Property,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication

from . import utils, worker_process
from .job import ACTIVE_STATES, TERMINAL_STATES, DownloadJob
from .queue_model import DownloadQueueModel

_SUPPORTED_LANGUAGES = ("en", "ru", "uz")
_POLL_INTERVAL_MS = 80
_CANCEL_WATCHDOG_MS = 2000


class DownloadManager(QObject):
    outputDirChanged = Signal()
    fileNameChanged = Signal()
    modeChanged = Signal()
    optionsChanged = Signal()
    resolutionOptionsChanged = Signal()
    languageChanged = Signal()

    jobAdded = Signal(str, arguments=["jobId"])
    previewChanged = Signal()
    playlistDetected = Signal(str, int, arguments=["jobId", "count"])
    loginRequested = Signal(str, str, arguments=["jobId", "url"])
    passwordRequested = Signal(str, str, arguments=["jobId", "url"])
    promptCancelled = Signal(str, arguments=["jobId"])
    notifyRequested = Signal(str, str, arguments=["title", "message"])
    errorOccurred = Signal(str, arguments=["message"])
    shutdownReady = Signal()

    def __init__(self, engine, translator, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._translator = translator
        self._settings = QSettings("elyor04", "VideoDownloader")

        self._queue_model = DownloadQueueModel(self)
        self._active: dict[str, DownloadJob] = {}
        self._fetching: dict[str, DownloadJob] = {}
        self._pending_prompts: list[tuple[str, str]] = []
        self._current_prompt_job_id: str | None = None

        self._mode = "video"
        self._resolution = utils.MAX_RESOLUTION
        self._convert_to = "original"
        self._file_name = ""
        self._output_dir = str(
            self._settings.value("outputDir", str(Path.home() / "Downloads"))
        )
        saved_language = self._settings.value("language", "")
        self._language = saved_language or self._detect_default_language()
        self._install_translator(self._language)

        self._preview_url = ""
        self._preview_state = "idle"  # idle | fetching | ready | error
        self._preview_title = ""
        self._preview_thumbnail = ""
        self._preview_is_playlist = False
        self._preview_playlist_count = None
        self._preview_max_height = None
        self._preview_error = ""
        self._preview_process = None
        self._preview_cmd_queue = None
        self._preview_event_queue = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._on_poll)
        self._poll_timer.start()

    # -- Add-job options exposed to QML --

    @Property(str, notify=modeChanged)
    def mode(self):
        return self._mode

    @Slot(str)
    def setMode(self, value):
        if value != self._mode:
            self._mode = value
            self.modeChanged.emit()
            self.optionsChanged.emit()

    def _effective_resolution_ladder(self):
        if not self._preview_max_height:
            return utils.RESOLUTION_LADDER
        # Once a preview has resolved the video's real max height, only
        # offer resolutions that actually exist for it (plus "Best").
        filtered = [
            entry for entry in utils.RESOLUTION_LADDER
            if entry[0] == utils.MAX_RESOLUTION or entry[0] <= self._preview_max_height
        ]
        return filtered or utils.RESOLUTION_LADDER

    @Property(list, notify=resolutionOptionsChanged)
    def resolutionModel(self):
        # Each entry carries its resolution value alongside its translated
        # label. QML reads the value straight off the selected entry (via
        # ComboBox.valueRole/currentValue) instead of an index that would
        # have to be re-resolved against whatever ladder is current by the
        # time the slot runs -- so a selection can never end up paired with
        # the wrong entry if the ladder is rebuilt in between.
        return [
            {"text": self.tr(label), "value": value}
            for value, label in self._effective_resolution_ladder()
        ]

    @Slot(int)
    def setResolution(self, value):
        if any(value == entry[0] for entry in utils.RESOLUTION_LADDER):
            self._resolution = value

    @Slot()
    def resetResolutionToBest(self):
        self._resolution = utils.MAX_RESOLUTION

    def _convert_option_values(self):
        return utils.AUDIO_CONVERT_OPTIONS if self._mode == "audio" else utils.VIDEO_CONVERT_OPTIONS

    @Property(list, notify=optionsChanged)
    def convertModel(self):
        # Same value-keyed pattern as resolutionModel -- see its docstring.
        return [
            {"text": self.tr(o) if o == "original" else o, "value": o}
            for o in self._convert_option_values()
        ]

    @Slot(str)
    def setConvertTo(self, value):
        # Validated against the *current* mode's options, not a fixed
        # global set: unlike resolution, video vs audio convert targets are
        # genuinely different domains -- accepting "mp3" while in video
        # mode would build a nonsensical ffmpeg postprocessor request.
        if value in self._convert_option_values():
            self._convert_to = value

    @Slot()
    def resetConvertToOriginal(self):
        self._convert_to = "original"

    @Property(str, notify=outputDirChanged)
    def outputDir(self):
        return self._output_dir

    @Slot(str)
    def setOutputDir(self, path):
        if path and path != self._output_dir:
            self._output_dir = path
            self._settings.setValue("outputDir", path)
            self.outputDirChanged.emit()

    @Slot(QUrl)
    def setOutputDirFromUrl(self, url):
        self.setOutputDir(url.toLocalFile())

    @Property(str, notify=fileNameChanged)
    def fileName(self):
        return self._file_name

    @Slot(str)
    def setFileName(self, value):
        self._file_name = value.strip()

    @Property(QObject, constant=True)
    def queueModel(self):
        return self._queue_model

    # -- URL preview (auto-fetched while the user is still typing/pasting) --

    @Property(str, notify=previewChanged)
    def previewUrl(self):
        return self._preview_url

    @Property(str, notify=previewChanged)
    def previewState(self):
        return self._preview_state

    @Property(str, notify=previewChanged)
    def previewTitle(self):
        return self._preview_title

    @Property(str, notify=previewChanged)
    def previewThumbnail(self):
        return self._preview_thumbnail

    @Property(bool, notify=previewChanged)
    def previewIsPlaylist(self):
        return self._preview_is_playlist

    @Property(int, notify=previewChanged)
    def previewPlaylistCount(self):
        return self._preview_playlist_count or 0

    @Property(str, notify=previewChanged)
    def previewError(self):
        return self._preview_error

    @Slot(str)
    def requestPreview(self, url):
        url = url.strip()
        if url == self._preview_url and self._preview_state in ("fetching", "ready"):
            return
        self._cancel_preview_process()
        self._preview_url = url
        had_max_height = self._preview_max_height is not None
        self._preview_max_height = None
        if not url:
            self._preview_state = "idle"
            self.previewChanged.emit()
            if had_max_height:
                self.resolutionOptionsChanged.emit()
            return
        self._preview_state = "fetching"
        self._preview_title = ""
        self._preview_thumbnail = ""
        self._preview_is_playlist = False
        self._preview_playlist_count = None
        self._preview_error = ""
        self.previewChanged.emit()
        if had_max_height:
            self.resolutionOptionsChanged.emit()

        cmd_q, event_q = Queue(), Queue()
        proc = Process(target=worker_process.run_fetch, args=(cmd_q, event_q, url), daemon=True)
        self._preview_process, self._preview_cmd_queue, self._preview_event_queue = proc, cmd_q, event_q
        proc.start()

    def _drain_preview(self):
        while True:
            try:
                kind, payload = self._preview_event_queue.get_nowait()
            except _queue.Empty:
                return
            if kind == "fetch_result":
                self._preview_title = payload.get("title") or self._preview_url
                self._preview_thumbnail = payload.get("thumbnail") or ""
                self._preview_is_playlist = bool(payload.get("is_playlist"))
                self._preview_playlist_count = payload.get("playlist_count")
                self._preview_max_height = payload.get("max_height")
                self._preview_state = "ready"
                self._finish_preview_process()
                self.previewChanged.emit()
                self.resolutionOptionsChanged.emit()
                return
            if kind == "error":
                self._preview_error = payload or ""
                self._preview_state = "error"
                self._finish_preview_process()
                self.previewChanged.emit()
                self.errorOccurred.emit(self._preview_error or self.tr("Couldn't load video info."))
                return

    def _finish_preview_process(self):
        if self._preview_process is not None:
            self._preview_process.join(timeout=1)
        self._preview_process = self._preview_cmd_queue = self._preview_event_queue = None

    def _cancel_preview_process(self):
        if self._preview_process is not None:
            if self._preview_process.is_alive():
                self._preview_process.terminate()
            self._preview_process.join(timeout=0.5)
        self._preview_process = self._preview_cmd_queue = self._preview_event_queue = None

    def _clear_preview(self):
        self._cancel_preview_process()
        had_max_height = self._preview_max_height is not None
        self._preview_url = ""
        self._preview_state = "idle"
        self._preview_title = ""
        self._preview_thumbnail = ""
        self._preview_is_playlist = False
        self._preview_playlist_count = None
        self._preview_max_height = None
        self._preview_error = ""
        self.previewChanged.emit()
        if had_max_height:
            self.resolutionOptionsChanged.emit()

    # -- Language --

    @Property(str, notify=languageChanged)
    def language(self):
        return self._language

    @Slot(str)
    def setLanguage(self, code):
        if code == self._language or code not in _SUPPORTED_LANGUAGES:
            return
        self._language = code
        self._settings.setValue("language", code)
        self._install_translator(code)
        self._engine.retranslate()
        self.languageChanged.emit()
        self.optionsChanged.emit()
        self.resolutionOptionsChanged.emit()

    def _detect_default_language(self):
        code = QLocale.system().name().split("_")[0].lower()
        return code if code in _SUPPORTED_LANGUAGES else "en"

    def _install_translator(self, code):
        QCoreApplication.removeTranslator(self._translator)
        if code != "en":
            qm_path = str(utils.resource_path(f"i18n/video_downloader_{code}.qm"))
            self._translator.load(qm_path)
            QCoreApplication.installTranslator(self._translator)

    # -- Adding jobs --

    @Slot(str)
    def addJob(self, url):
        url = url.strip()
        if not url:
            self.errorOccurred.emit(self.tr("Please enter a video URL."))
            return
        dir_error = utils.check_download_dir(self._output_dir, create=True)
        if dir_error:
            self.errorOccurred.emit(self.tr(dir_error))
            return

        job = DownloadJob(
            url=url,
            mode=self._mode,
            resolution=self._resolution,
            convert_to=self._convert_to,
            output_dir=self._output_dir,
            file_name=self._file_name or "%(title)s",
        )

        if url == self._preview_url and self._preview_state == "ready":
            # Already have fresh metadata from the auto-preview -- use it
            # directly instead of spawning a second, redundant fetch.
            job.title = self._preview_title
            job.thumbnail = self._preview_thumbnail
            job.is_playlist = self._preview_is_playlist
            job.playlist_count = self._preview_playlist_count
            self._queue_model.add_job(job)
            if job.is_playlist:
                self._transition(job, "awaiting_playlist_confirm")
                self._request_prompt(job.id, "playlist")
            else:
                self._transition(job, "queued")
        else:
            self._queue_model.add_job(job)
            self._start_fetch(job)

        self._clear_preview()
        self.jobAdded.emit(job.id)

    def _start_fetch(self, job):
        cmd_q, event_q = Queue(), Queue()
        proc = Process(
            target=worker_process.run_fetch,
            args=(cmd_q, event_q, job.url),
            daemon=True,
        )
        job.process, job.cmd_queue, job.event_queue = proc, cmd_q, event_q
        self._fetching[job.id] = job
        proc.start()

    # -- Poll loop: drains worker events, then schedules queued jobs --

    def _on_poll(self):
        # An unhandled exception escaping a slot invoked from Qt's C++ event
        # loop (rather than from ordinary Python code) risks aborting the
        # whole app instead of just the job being processed -- defeating the
        # per-job isolation the worker-process design is meant to provide.
        # Guard each job independently so one bad event can't take down the
        # others still in flight.
        if self._preview_event_queue is not None:
            self._guarded(self._drain_preview)
        for job in list(self._fetching.values()):
            self._guarded(self._drain, job, is_fetch=True)
        for job in list(self._active.values()):
            self._guarded(self._drain, job, is_fetch=False)
        self._schedule_next()

    def _guarded(self, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception:
            traceback.print_exc()

    def _drain(self, job, is_fetch):
        finished_process = False
        last_progress = None
        while True:
            try:
                kind, payload = job.event_queue.get_nowait()
            except _queue.Empty:
                break
            if kind == "progress":
                last_progress = payload
                continue
            if is_fetch:
                finished_process = self._handle_fetch_event(job, kind, payload)
            else:
                finished_process = self._handle_download_event(job, kind, payload)
            if finished_process:
                break
        if last_progress is not None and job.state == "downloading":
            self._apply_progress(job, last_progress)
        if finished_process:
            self._finalize_process(job, is_fetch)

    def _handle_fetch_event(self, job, kind, payload):
        if kind == "fetch_result":
            job.title = payload.get("title") or job.url
            job.thumbnail = payload.get("thumbnail") or ""
            job.is_playlist = bool(payload.get("is_playlist"))
            job.playlist_count = payload.get("playlist_count")
            if job.is_playlist:
                self._transition(job, "awaiting_playlist_confirm")
                self._request_prompt(job.id, "playlist")
            else:
                self._transition(job, "queued")
            return True
        if kind == "error":
            job.error_message = payload or ""
            self._transition(job, "error")
            return True
        return False

    def _handle_download_event(self, job, kind, payload):
        if kind == "stage":
            job.stage = payload
            self._queue_model.notify_row_changed(job.id)
            return False
        if kind == "login_request":
            self._transition(job, "awaiting_login")
            self._request_prompt(job.id, "login")
            return False
        if kind == "password_request":
            self._transition(job, "awaiting_password")
            self._request_prompt(job.id, "password")
            return False
        if kind == "finished":
            job.finished_dir = payload or job.output_dir
            job.progress = 1.0
            self._transition(job, "success")
            self._notify_if_unfocused(job, success=True)
            return True
        if kind == "cancelled":
            self._transition(job, "cancelled")
            return True
        if kind == "error":
            job.error_message = payload or ""
            self._transition(job, "error")
            self._notify_if_unfocused(job, success=False)
            return True
        return False

    def _apply_progress(self, job, payload):
        downloaded = payload.get("downloaded_bytes")
        total = payload.get("total_bytes")
        speed = payload.get("speed")
        eta = payload.get("eta")
        job.downloaded_bytes = downloaded if downloaded is not None else -1
        job.total_bytes = total if total is not None else -1
        job.speed = speed if speed is not None else -1
        job.eta = eta if eta is not None else -1
        job.playlist_index = payload.get("playlist_index")
        n_entries = payload.get("n_entries")
        if n_entries:
            job.playlist_count = n_entries
        if payload.get("status") == "finished" or job.total_bytes <= 0 or job.downloaded_bytes < 0:
            job.progress = -1.0
        else:
            job.progress = job.downloaded_bytes / job.total_bytes
        job.stage = "downloading"
        self._queue_model.notify_row_changed(job.id)

    def _finalize_process(self, job, is_fetch):
        (self._fetching if is_fetch else self._active).pop(job.id, None)
        if job.process is not None:
            job.process.join(timeout=1)
        job.process = job.cmd_queue = job.event_queue = job.cancel_event = None

    def _transition(self, job, state):
        job.set_state(state)
        self._queue_model.notify_row_changed(job.id)

    # -- Concurrency scheduler --

    def _schedule_next(self):
        while len(self._active) < utils.MAX_CONCURRENT_DOWNLOADS:
            job = next((j for j in self._queue_model.jobs() if j.state == "queued"), None)
            if job is None:
                break
            self._start_download(job)

    def _start_download(self, job):
        cmd_q, event_q, cancel_ev = Queue(), Queue(), MpEvent()
        params = {
            "url": job.url,
            "mode": job.mode,
            "resolution": job.resolution,
            "convert_to": job.convert_to,
            "output_dir": job.output_dir,
            "file_name": job.file_name,
            "is_playlist": job.is_playlist,
            "download_playlist": job.download_playlist,
        }
        proc = Process(
            target=worker_process.run_download,
            args=(cmd_q, event_q, cancel_ev, params),
            daemon=True,
        )
        job.process, job.cmd_queue, job.event_queue, job.cancel_event = (
            proc, cmd_q, event_q, cancel_ev,
        )
        self._active[job.id] = job
        self._transition(job, "downloading")
        proc.start()

    # -- Modal prompt serialization (playlist confirm / login / password) --

    def _request_prompt(self, job_id, kind):
        self._pending_prompts.append((job_id, kind))
        self._maybe_show_next_prompt()

    def _maybe_show_next_prompt(self):
        if self._current_prompt_job_id is not None or not self._pending_prompts:
            return
        job_id, kind = self._pending_prompts.pop(0)
        job = self._queue_model.job_by_id(job_id)
        if job is None:
            self._maybe_show_next_prompt()
            return
        self._current_prompt_job_id = job_id
        if kind == "playlist":
            self.playlistDetected.emit(job_id, job.playlist_count or 0)
        elif kind == "login":
            self.loginRequested.emit(job_id, job.url)
        elif kind == "password":
            self.passwordRequested.emit(job_id, job.url)

    def _dismiss_prompts_for(self, job_id):
        self._pending_prompts = [p for p in self._pending_prompts if p[0] != job_id]
        if self._current_prompt_job_id == job_id:
            self._current_prompt_job_id = None
            self.promptCancelled.emit(job_id)
            self._maybe_show_next_prompt()

    def _clear_current_prompt(self, job_id):
        if self._current_prompt_job_id == job_id:
            self._current_prompt_job_id = None
        self._maybe_show_next_prompt()

    @Slot(str, bool)
    def confirmPlaylist(self, job_id, download_all):
        job = self._queue_model.job_by_id(job_id)
        if job is not None and job.state == "awaiting_playlist_confirm":
            job.download_playlist = download_all
            self._transition(job, "queued")
        self._clear_current_prompt(job_id)

    @Slot(str, str, str)
    def submitLogin(self, job_id, username, password):
        job = self._queue_model.job_by_id(job_id)
        # Guard against a stale/duplicate submit (e.g. a rapid double-click
        # on the dialog button before it closes) re-entering here after the
        # job has already left "awaiting_login" -- without this, a second
        # call would try an invalid "downloading" -> "downloading"
        # transition and hit the assertion in job.set_state.
        if job is not None and job.state == "awaiting_login" and job.cmd_queue is not None:
            job.cmd_queue.put(("login", (username, password)))
            self._transition(job, "downloading")
        self._clear_current_prompt(job_id)

    @Slot(str, str)
    def submitPassword(self, job_id, password):
        job = self._queue_model.job_by_id(job_id)
        if job is not None and job.state == "awaiting_password" and job.cmd_queue is not None:
            job.cmd_queue.put(("password", password))
            self._transition(job, "downloading")
        self._clear_current_prompt(job_id)

    @Slot(str)
    def skipAuthentication(self, job_id):
        job = self._queue_model.job_by_id(job_id)
        if job is not None and job.cmd_queue is not None and job.state in ("awaiting_login", "awaiting_password"):
            kind = "login" if job.state == "awaiting_login" else "password"
            job.cmd_queue.put((kind, None))
            self._transition(job, "downloading")
        self._clear_current_prompt(job_id)

    # -- Cancel / remove --

    @Slot(str)
    def cancelJob(self, job_id):
        job = self._queue_model.job_by_id(job_id)
        if job is None or job.state in TERMINAL_STATES:
            return
        self._dismiss_prompts_for(job.id)
        if job.cancel_event is not None:
            job.cancel_event.set()
            QTimer.singleShot(_CANCEL_WATCHDOG_MS, lambda: self._force_kill(job))
            return
        # No cooperative-cancel channel (still fetching, or not started yet): resolve now.
        is_fetch = job.id in self._fetching
        if job.process is not None and job.process.is_alive():
            job.process.terminate()
        self._finalize_process(job, is_fetch)
        self._transition(job, "cancelled")

    def _force_kill(self, job):
        if job.state in TERMINAL_STATES:
            return
        is_fetch = job.id in self._fetching
        if job.process is not None and job.process.is_alive():
            # Only reached for download jobs (scheduled from the
            # cancel_event branch of cancelJob), which own their process
            # group -- safe to take ffmpeg down with them.
            utils.terminate_process_tree(job.process)
        self._finalize_process(job, is_fetch)
        self._transition(job, "cancelled")

    @Slot(str)
    def removeJob(self, job_id):
        job = self._queue_model.job_by_id(job_id)
        if job is None or job.state not in TERMINAL_STATES:
            return
        self._queue_model.remove_job(job_id)

    @Slot()
    def cancelAll(self):
        for job in self._queue_model.jobs():
            if job.state in ACTIVE_STATES:
                self.cancelJob(job.id)

    @Slot()
    def clearCompleted(self):
        for job in self._queue_model.jobs():
            if job.state in TERMINAL_STATES:
                self._queue_model.remove_job(job.id)

    @Slot(str)
    def openOutputFolder(self, job_id):
        job = self._queue_model.job_by_id(job_id)
        if job is not None and job.state == "success":
            utils.open_in_file_manager(job.finished_dir or job.output_dir)

    # -- Notifications --

    def _notify_if_unfocused(self, job, success):
        app = QGuiApplication.instance()
        if app is not None and app.applicationState() == Qt.ApplicationState.ApplicationActive:
            return
        title = self.tr("Download finished") if success else self.tr("Download failed")
        self.notifyRequested.emit(title, job.title or job.url)

    # -- Shutdown --

    @Slot()
    def requestShutdown(self):
        self._poll_timer.stop()
        self._cancel_preview_process()
        jobs = [*self._active.values(), *self._fetching.values()]
        for job in jobs:
            if job.cancel_event is not None:
                job.cancel_event.set()
        for job in jobs:
            if job.process is None:
                continue
            job.process.join(timeout=1.5)
            if job.process.is_alive():
                # Download jobs own their process group (see worker_process
                # .run_download); fetch jobs don't spawn ffmpeg and share the
                # app's group, so they must only ever get a plain terminate.
                if job.cancel_event is not None:
                    utils.terminate_process_tree(job.process)
                else:
                    job.process.terminate()
                job.process.join(timeout=1)
        self.shutdownReady.emit()
