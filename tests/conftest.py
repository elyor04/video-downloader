import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PySide6.QtCore import QCoreApplication


@pytest.fixture(scope="session")
def qt_app():
    """A QCoreApplication is required for QObject machinery (QTimer,
    QAbstractListModel, ...) used by the backend, even in tests that never
    run an actual event loop.
    """
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv[:1])
    return app
