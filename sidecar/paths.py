import os
from pathlib import Path

# State that must exist before settings can be read (DB file lives here).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_STATE_DIR = Path(os.environ.get("MICRO_STATE_DIR", PROJECT_ROOT / "data"))
DB_PATH = APP_STATE_DIR / "app.db"

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DEV_VIDEO_PATH = FIXTURES_DIR / "dev_microscopy.mp4"


def ensure_state_dir() -> None:
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)


def get_data_dir() -> Path:
    """User-configured directory for sessions, clips, snapshots."""
    # Imported lazily to avoid a circular import (settings_service -> db init).
    from sidecar.settings_service import get_settings

    return Path(get_settings().data_dir)


def get_sessions_dir() -> Path:
    p = get_data_dir() / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p
