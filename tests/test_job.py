import pytest

from DownloaderApp.backend.job import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    DownloadJob,
)


def make_job(**overrides):
    defaults = dict(
        url="https://example.com/video",
        mode="video",
        resolution=1080,
        convert_to="original",
        output_dir="/tmp",
        file_name="%(title)s",
    )
    defaults.update(overrides)
    return DownloadJob(**defaults)


def test_new_job_starts_in_fetching_state():
    assert make_job().state == "fetching"


def test_each_job_gets_a_unique_id():
    assert make_job().id != make_job().id


@pytest.mark.parametrize(
    "from_state, to_state",
    [(frm, to) for frm, tos in VALID_TRANSITIONS.items() for to in tos],
)
def test_valid_transitions_succeed(from_state, to_state):
    job = make_job()
    job.state = from_state
    job.set_state(to_state)
    assert job.state == to_state


@pytest.mark.parametrize(
    "from_state, to_state",
    [
        (frm, to)
        for frm in VALID_TRANSITIONS
        for to in set(VALID_TRANSITIONS) - VALID_TRANSITIONS[frm]
    ],
)
def test_invalid_transitions_raise(from_state, to_state):
    job = make_job()
    job.state = from_state
    with pytest.raises(AssertionError):
        job.set_state(to_state)


def test_terminal_states_allow_no_further_transitions():
    for state in TERMINAL_STATES:
        assert VALID_TRANSITIONS[state] == set()


def test_active_and_terminal_states_partition_all_states():
    all_states = set(VALID_TRANSITIONS)
    assert ACTIVE_STATES | TERMINAL_STATES == all_states
    assert ACTIVE_STATES & TERMINAL_STATES == set()
