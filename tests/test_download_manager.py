import pytest
from PySide6.QtCore import QTranslator

from DownloaderApp.backend import utils
from DownloaderApp.backend.download_manager import DownloadManager
from DownloaderApp.backend.job import DownloadJob


class _StubEngine:
    def retranslate(self):
        pass


class _FakeSettings:
    """Stand-in for QSettings that never touches real OS-level storage
    (the registry on Windows, plist on macOS, ...) just to run a test."""

    def __init__(self, *args, **kwargs):
        self._data = {}

    def value(self, key, default=None):
        return self._data.get(key, default)

    def setValue(self, key, value):
        self._data[key] = value


class _FakeCmdQueue:
    def __init__(self):
        self.put_calls = []

    def put(self, item):
        self.put_calls.append(item)


@pytest.fixture
def manager(qt_app, monkeypatch):
    monkeypatch.setattr(
        "DownloaderApp.backend.download_manager.QSettings", _FakeSettings
    )
    mgr = DownloadManager(_StubEngine(), QTranslator())
    yield mgr
    mgr._poll_timer.stop()


def _add_job(manager, state):
    job = DownloadJob(
        url="https://example.com/video",
        mode="video",
        resolution=1080,
        convert_to="original",
        output_dir="/tmp",
        file_name="%(title)s",
    )
    job.state = state
    job.cmd_queue = _FakeCmdQueue()
    manager.queueModel.add_job(job)
    return job


def test_submit_login_transitions_job_to_downloading(manager):
    job = _add_job(manager, "awaiting_login")
    manager.submitLogin(job.id, "user", "pass")
    assert job.state == "downloading"
    assert job.cmd_queue.put_calls == [("login", ("user", "pass"))]


def test_submit_password_transitions_job_to_downloading(manager):
    job = _add_job(manager, "awaiting_password")
    manager.submitPassword(job.id, "secret")
    assert job.state == "downloading"
    assert job.cmd_queue.put_calls == [("password", "secret")]


def test_skip_authentication_transitions_job_to_downloading(manager):
    job = _add_job(manager, "awaiting_login")
    manager.skipAuthentication(job.id)
    assert job.state == "downloading"
    assert job.cmd_queue.put_calls == [("login", None)]


# Regression tests for the double-submit edge case: a rapid double-click on
# a dialog button (Sign In / Submit / Skip) could re-enter these slots
# after the job had already left its "awaiting_*" state, so a second call
# would attempt an invalid "downloading" -> "downloading" transition and
# hit the assertion in job.set_state. Each slot now checks job.state
# before acting, matching the guard confirmPlaylist already had.


def test_double_submit_login_does_not_raise(manager):
    job = _add_job(manager, "awaiting_login")
    manager.submitLogin(job.id, "user", "pass")
    assert job.state == "downloading"

    manager.submitLogin(job.id, "user", "pass")  # stale second click
    assert job.state == "downloading"
    assert len(job.cmd_queue.put_calls) == 1


def test_double_submit_password_does_not_raise(manager):
    job = _add_job(manager, "awaiting_password")
    manager.submitPassword(job.id, "secret")
    assert job.state == "downloading"

    manager.submitPassword(job.id, "secret")
    assert job.state == "downloading"
    assert len(job.cmd_queue.put_calls) == 1


def test_double_skip_authentication_does_not_raise(manager):
    job = _add_job(manager, "awaiting_login")
    manager.skipAuthentication(job.id)
    assert job.state == "downloading"

    manager.skipAuthentication(job.id)
    assert job.state == "downloading"
    assert len(job.cmd_queue.put_calls) == 1


def test_submit_login_after_job_already_cancelled_is_ignored(manager):
    job = _add_job(manager, "awaiting_login")
    job.state = "cancelled"
    manager.submitLogin(job.id, "user", "pass")  # must not raise
    assert job.state == "cancelled"
    assert job.cmd_queue.put_calls == []


# -- resolution selection --
# resolutionModel/setResolution are value-keyed rather than index-keyed:
# QML reads a selection's resolution value straight off the chosen entry
# (via ComboBox.valueRole/currentValue) instead of handing back an index
# that Python would have to re-resolve against whatever ladder happens to
# be current. See the docstring on setResolution/resolutionModel for why.


def test_resolution_model_reflects_full_ladder_by_default(manager):
    values = [entry["value"] for entry in manager.resolutionModel]
    assert values == [v for v, _ in utils.RESOLUTION_LADDER]


def test_resolution_model_narrows_to_preview_max_height(manager):
    manager._preview_max_height = 480
    values = [entry["value"] for entry in manager.resolutionModel]
    assert utils.MAX_RESOLUTION in values  # "Best" always stays available
    assert all(v == utils.MAX_RESOLUTION or v <= 480 for v in values)
    assert 1080 not in values


def test_set_resolution_accepts_a_valid_value(manager):
    manager.setResolution(720)
    assert manager._resolution == 720


def test_set_resolution_rejects_a_value_not_on_the_ladder(manager):
    manager._resolution = 720
    manager.setResolution(999999)
    assert manager._resolution == 720  # unchanged


def test_reset_resolution_to_best(manager):
    manager._resolution = 720
    manager.resetResolutionToBest()
    assert manager._resolution == utils.MAX_RESOLUTION


def test_selection_survives_ladder_narrowing_after_the_fact(manager):
    """This is the exact scenario the old index-based design was fragile
    to: an entry is chosen from one ladder (e.g. the user picks "1080p"
    from the full list), then the ladder narrows -- a preview resolves and
    filters it down -- before the selection reaches the backend. Since the
    resolution value travels with the selection instead of a bare index,
    applying it after the narrowing still resolves to the right entry;
    with the old design, that same index would now point at a completely
    different, unrelated entry in the shrunk list.
    """
    chosen_value = 1080  # picked while the full ladder was on screen

    manager.setResolution(chosen_value)
    assert manager._resolution == chosen_value

    # The ladder now narrows underneath the already-made selection (e.g. a
    # preview resolves to a lower max height).
    manager._preview_max_height = 480
    narrowed_values = [entry["value"] for entry in manager.resolutionModel]
    assert chosen_value not in narrowed_values  # confirms it actually narrowed

    # The earlier selection is untouched -- nothing re-resolves it against
    # the now-different ladder, because nothing ever needs to.
    assert manager._resolution == chosen_value


# -- convert-format selection --
# Same value-keyed pattern as resolution, but validated against the
# *current* mode's options rather than a fixed global set: video and audio
# convert targets are genuinely different domains (see setConvertTo).


def test_convert_model_reflects_video_options_by_default(manager):
    values = [entry["value"] for entry in manager.convertModel]
    assert values == utils.VIDEO_CONVERT_OPTIONS


def test_convert_model_reflects_audio_options_in_audio_mode(manager):
    manager.setMode("audio")
    values = [entry["value"] for entry in manager.convertModel]
    assert values == utils.AUDIO_CONVERT_OPTIONS


def test_set_convert_to_accepts_a_valid_value_for_current_mode(manager):
    manager.setConvertTo("mp4")
    assert manager._convert_to == "mp4"


def test_set_convert_to_rejects_value_from_the_other_mode(manager):
    # manager starts in "video" mode; "mp3" only makes sense in "audio".
    manager._convert_to = "original"
    manager.setConvertTo("mp3")
    assert manager._convert_to == "original"  # unchanged


def test_reset_convert_to_original(manager):
    manager.setConvertTo("mkv")
    manager.resetConvertToOriginal()
    assert manager._convert_to == "original"
