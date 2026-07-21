import os
import subprocess
import sys
from multiprocessing import Process
from multiprocessing import Queue as MPQueue

import pytest

from DownloaderApp.backend import utils


# -- formatters --

@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "?"),
        (-1, "?"),
        (0, "0.0 B"),
        (512, "512.0 B"),
        (1024, "1.0 KB"),
        (1024 * 1024, "1.0 MB"),
        (1024**3, "1.0 GB"),
        (1024**4, "1.0 TB"),
    ],
)
def test_format_bytes(value, expected):
    assert utils.format_bytes(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "?"),
        (-1, "?"),
        (0, "0.0 B/s"),
        (2048, "2.0 KB/s"),
    ],
)
def test_format_speed(value, expected):
    assert utils.format_speed(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "?"),
        (-1, "?"),
        (0, "0:00"),
        (65, "1:05"),
        (3661, "1:01:01"),
    ],
)
def test_format_eta(value, expected):
    assert utils.format_eta(value) == expected


# -- check_download_dir --

def test_check_download_dir_existing_writable_dir(tmp_path):
    assert utils.check_download_dir(str(tmp_path)) is None


def test_check_download_dir_missing_without_create(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert utils.check_download_dir(str(missing)) == "Not a directory"


def test_check_download_dir_creates_missing_dir(tmp_path):
    target = tmp_path / "nested" / "downloads"
    assert utils.check_download_dir(str(target), create=True) is None
    assert target.is_dir()


def test_check_download_dir_path_is_a_file(tmp_path):
    f = tmp_path / "not-a-dir"
    f.write_text("x")
    assert utils.check_download_dir(str(f), create=True) == "Not a directory"


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="permission enforcement isn't testable as root or on Windows this way",
)
def test_check_download_dir_unwritable_parent_reports_could_not_create(tmp_path):
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(0o500)  # r-x, no write
    target = parent / "child"
    try:
        assert (
            utils.check_download_dir(str(target), create=True)
            == "Could not create directory"
        )
    finally:
        parent.chmod(0o700)  # restore so tmp_path cleanup can remove it


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="exercises the FileNotFoundError path os.makedirs takes on Windows "
    "when a parent component is a file; POSIX raises NotADirectoryError instead "
    "but check_download_dir handles both the same way (any OSError)",
)
def test_check_download_dir_parent_is_a_file_reports_could_not_create_windows(tmp_path):
    parent_as_file = tmp_path / "not-a-dir"
    parent_as_file.write_text("x")
    target = parent_as_file / "child"
    assert (
        utils.check_download_dir(str(target), create=True)
        == "Could not create directory"
    )


# -- terminate_process_tree --
# Regression coverage for the orphaned-ffmpeg bug: cancelling a download
# used to kill only the worker process, leaving any subprocess it spawned
# (ffmpeg, via yt-dlp's postprocessors) running in the background. These
# tests stand a real subprocess in for ffmpeg and confirm the process-group
# kill takes it down along with the worker.


def _spawn_child_process(ready_queue):
    if hasattr(os, "setsid"):
        os.setsid()
    child = subprocess.Popen(["sleep", "30"])
    ready_queue.put(child.pid)
    child.wait()


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _do_nothing():
    pass


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX process-group mechanism; Windows path uses taskkill /T",
)
def test_terminate_process_tree_kills_worker_and_its_child():
    ready_queue = MPQueue()
    proc = Process(target=_spawn_child_process, args=(ready_queue,), daemon=True)
    proc.start()
    try:
        child_pid = ready_queue.get(timeout=5)
        assert proc.is_alive()
        assert _pid_alive(child_pid)

        utils.terminate_process_tree(proc)
        proc.join(timeout=3)

        assert not proc.is_alive()
        assert not _pid_alive(child_pid)
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1)


def _spawn_child_process_windows(ready_queue):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    ready_queue.put(child.pid)
    child.wait()


def _pid_alive_windows(pid):
    # os.kill(pid, 0) doesn't reliably report exit status on Windows, so shell
    # out to tasklist and check whether the PID still shows up.
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True
    )
    return str(pid) in result.stdout


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-only taskkill /T process-tree mechanism",
)
def test_terminate_process_tree_kills_worker_and_its_child_windows():
    ready_queue = MPQueue()
    proc = Process(
        target=_spawn_child_process_windows, args=(ready_queue,), daemon=True
    )
    proc.start()
    try:
        child_pid = ready_queue.get(timeout=5)
        assert proc.is_alive()
        assert _pid_alive_windows(child_pid)

        utils.terminate_process_tree(proc)
        proc.join(timeout=5)

        assert not proc.is_alive()
        assert not _pid_alive_windows(child_pid)
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1)


def test_terminate_process_tree_on_already_dead_process_is_a_no_op():
    proc = Process(target=_do_nothing, daemon=True)
    proc.start()
    proc.join(timeout=3)
    assert not proc.is_alive()

    utils.terminate_process_tree(proc)  # must not raise
