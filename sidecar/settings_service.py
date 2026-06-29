"""Settings singleton (id=1) accessor with an in-memory cache.

Reads are hot (every file path lookup uses them) so we cache the row and
invalidate when an update comes in.
"""

import threading
from pathlib import Path

from sqlmodel import Session as DbSession

from sidecar.db import engine
from sidecar.image_processing import ImageProcessor, ProcessingParams
from sidecar.models import Settings

_lock = threading.Lock()
_cached: Settings | None = None
_processor = ImageProcessor()


def default_data_dir() -> Path:
    """Pictures/Microorganism Classifier by default, mac-style."""
    return Path.home() / "Pictures" / "Microorganism Classifier"


def processor() -> ImageProcessor:
    return _processor


def _sync_processor(row: Settings) -> None:
    _processor.set(
        ProcessingParams(
            brightness=row.brightness,
            contrast=row.contrast,
            gamma=row.gamma,
            wb_r=row.wb_r,
            wb_g=row.wb_g,
            wb_b=row.wb_b,
            invert=row.invert,
            local_contrast=row.local_contrast,
            sharpness=row.sharpness,
            grayscale=row.grayscale,
        )
    )


def get_settings() -> Settings:
    global _cached
    if _cached is not None:
        return _cached
    with _lock:
        if _cached is not None:
            return _cached
        with DbSession(engine) as s:
            row = s.get(Settings, 1)
            if row is None:
                dd = default_data_dir()
                dd.mkdir(parents=True, exist_ok=True)
                row = Settings(id=1, data_dir=str(dd))
                s.add(row)
                s.commit()
                s.refresh(row)
            _cached = row
            _sync_processor(row)
            return row


def update_settings(**changes) -> Settings:
    global _cached
    with _lock, DbSession(engine) as s:
        row = s.get(Settings, 1) or Settings(id=1, data_dir=str(default_data_dir()))
        for k, v in changes.items():
            if v is None:
                continue
            setattr(row, k, v)
        # Ensure data_dir exists if it was changed
        if "data_dir" in changes and changes["data_dir"] is not None:
            Path(row.data_dir).mkdir(parents=True, exist_ok=True)
        s.add(row)
        s.commit()
        s.refresh(row)
        _cached = row
        _sync_processor(row)
        return row


def invalidate_cache() -> None:
    """Force the next get_settings() to re-read from disk."""
    global _cached
    with _lock:
        _cached = None
