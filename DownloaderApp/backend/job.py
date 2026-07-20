import dataclasses
import uuid
from typing import Optional

# Job state machine:
#   fetching -> awaiting_playlist_confirm -> queued -> downloading -> success
#                                                    \-> awaiting_login -----/  (loops back into downloading)
#                                                    \-> awaiting_password -/
#   any non-terminal state -> cancelled (via user action)
#   fetching / downloading -> error
VALID_TRANSITIONS: dict[str, set[str]] = {
    "fetching": {"queued", "awaiting_playlist_confirm", "error", "cancelled"},
    "awaiting_playlist_confirm": {"queued", "cancelled"},
    "queued": {"downloading", "cancelled"},
    "downloading": {
        "awaiting_login", "awaiting_password", "success", "error", "cancelled",
    },
    "awaiting_login": {"downloading", "cancelled"},
    "awaiting_password": {"downloading", "cancelled"},
    "success": set(),
    "error": set(),
    "cancelled": set(),
}

ACTIVE_STATES = {
    "fetching", "awaiting_playlist_confirm", "queued",
    "awaiting_login", "awaiting_password", "downloading",
}
TERMINAL_STATES = {"success", "error", "cancelled"}


@dataclasses.dataclass
class DownloadJob:
    url: str
    mode: str  # "video" | "audio"
    resolution: int
    convert_to: str
    output_dir: str
    file_name: str

    id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    state: str = "fetching"

    title: str = ""
    thumbnail: str = ""
    error_message: str = ""

    is_playlist: bool = False
    playlist_count: Optional[int] = None
    download_playlist: bool = True

    progress: float = -1.0  # 0..1, negative = indeterminate/unknown
    downloaded_bytes: int = -1
    total_bytes: int = -1
    speed: int = -1
    eta: int = -1
    playlist_index: Optional[int] = None
    stage: str = "downloading"  # "downloading" | "converting"

    finished_dir: str = ""

    # Populated only while the job has a running child process.
    process: object = None
    cmd_queue: object = None
    event_queue: object = None
    cancel_event: object = None

    def set_state(self, new_state: str) -> None:
        allowed = VALID_TRANSITIONS.get(self.state, set())
        assert new_state in allowed, f"invalid job transition {self.state!r} -> {new_state!r}"
        self.state = new_state
