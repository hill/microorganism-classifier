"""SQLModel table classes and request schemas.

Models with `table=True` map to SQLite tables. Models without are request schemas.
Imported by Alembic env.py via SQLModel.metadata to drive migration autogeneration.
"""

from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

# SQLAlchemy parses relationship type annotations as forward-reference strings.
# It cannot resolve PEP 604 unions like `"Recording | None"`, so for the optional
# back-relationship from Run to Recording we keep `Optional["Recording"]`.


def _now() -> datetime:
    return datetime.now(UTC)


class Session(SQLModel, table=True):
    __tablename__ = "session"
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = None
    notes: str | None = None

    samples: list["Sample"] = Relationship(back_populates="session", cascade_delete=True)


class Sample(SQLModel, table=True):
    __tablename__ = "sample"
    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session.id", index=True)
    collected_at: datetime | None = None
    site: str | None = None
    depth_cm: float | None = None
    container: str | None = None
    preparation: str | None = None
    notes: str | None = None

    session: Session = Relationship(back_populates="samples")
    runs: list["Run"] = Relationship(back_populates="sample", cascade_delete=True)


class Run(SQLModel, table=True):
    __tablename__ = "run"
    id: int | None = Field(default=None, primary_key=True)
    sample_id: int = Field(foreign_key="sample.id", index=True)
    started_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = None
    objective: str | None = None
    illumination: str | None = None
    camera_settings: str | None = None

    sample: Sample = Relationship(back_populates="runs")
    tracks: list["Track"] = Relationship(back_populates="run", cascade_delete=True)
    recording: Optional["Recording"] = Relationship(back_populates="run", cascade_delete=True)
    snapshots: list["Snapshot"] = Relationship(back_populates="run", cascade_delete=True)
    clips: list["Clip"] = Relationship(back_populates="run", cascade_delete=True)


class Recording(SQLModel, table=True):
    __tablename__ = "recording"
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True, unique=True)
    path: str
    fps: float
    width: int
    height: int
    duration_ms: int | None = None

    run: Run = Relationship(back_populates="recording")


class Track(SQLModel, table=True):
    __tablename__ = "track"
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    label: str | None = Field(default=None, index=True)
    first_frame_ts: datetime
    last_frame_ts: datetime
    start_video_ms: int
    end_video_ms: int
    n_frames: int
    mask_path: str | None = None
    mean_area_px: float | None = None
    bbox_w_px: float | None = None
    bbox_h_px: float | None = None
    mean_speed_px_s: float | None = None
    flagged: bool = Field(default=False, index=True)
    notes: str | None = None

    run: Run = Relationship(back_populates="tracks")
    frames: list["Frame"] = Relationship(back_populates="track", cascade_delete=True)


class Frame(SQLModel, table=True):
    __tablename__ = "frame"
    id: int | None = Field(default=None, primary_key=True)
    track_id: int = Field(foreign_key="track.id", index=True)
    ts: datetime
    path: str
    sharpness: float | None = None

    track: Track = Relationship(back_populates="frames")


class Snapshot(SQLModel, table=True):
    __tablename__ = "snapshot"
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    ts: datetime = Field(default_factory=_now)
    path: str
    label: str | None = Field(default=None, index=True)
    flagged: bool = Field(default=False, index=True)
    notes: str | None = None

    run: Run = Relationship(back_populates="snapshots")


class Clip(SQLModel, table=True):
    __tablename__ = "clip"
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    started_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = None
    path: str
    seconds_before: float = 0.0
    duration_ms: int | None = None
    label: str | None = Field(default=None, index=True)
    flagged: bool = Field(default=False, index=True)
    notes: str | None = None

    run: Run = Relationship(back_populates="clips")


# Request schemas
class SessionCreate(SQLModel):
    notes: str | None = None


class SampleCreate(SQLModel):
    session_id: int
    collected_at: datetime | None = None
    site: str | None = None
    depth_cm: float | None = None
    container: str | None = None
    preparation: str | None = None
    notes: str | None = None


class RunCreate(SQLModel):
    sample_id: int
    objective: str | None = None
    illumination: str | None = None
    camera_settings: str | None = None


class LabelSet(SQLModel):
    label: str


class FlagSet(SQLModel):
    flagged: bool


class NotesSet(SQLModel):
    notes: str


class ClipStart(SQLModel):
    sample_id: int
    seconds_before: float = 30.0


class Settings(SQLModel, table=True):
    __tablename__ = "settings"
    id: int = Field(default=1, primary_key=True)
    data_dir: str
    # Which camera (cv2 device index) to open.
    device_index: int = Field(default=0)
    # Image processing parameters applied to every live frame.
    brightness: int = Field(default=0)  # -100..100
    contrast: float = Field(default=1.0)  # 0.3..2.5
    gamma: float = Field(default=1.0)  # 0.3..3.0
    wb_r: float = Field(default=1.0)  # 0.3..2.5
    wb_g: float = Field(default=1.0)
    wb_b: float = Field(default=1.0)
    invert: bool = Field(default=False)
    local_contrast: float = Field(default=0.0)  # CLAHE clip limit, 0 disables
    sharpness: float = Field(default=0.0)  # unsharp mask amount, 0 disables
    grayscale: bool = Field(default=False)


class SettingsUpdate(SQLModel):
    data_dir: str | None = None
    device_index: int | None = None
    brightness: int | None = None
    contrast: float | None = None
    gamma: float | None = None
    wb_r: float | None = None
    wb_g: float | None = None
    wb_b: float | None = None
    invert: bool | None = None
    local_contrast: float | None = None
    sharpness: float | None = None
    grayscale: bool | None = None


class CameraInfo(SQLModel):
    index: int
    name: str
    width: int
    height: int


class TrackRead(SQLModel):
    """Track row plus its frames and source clip, for the detail endpoint."""

    id: int
    run_id: int
    label: str | None
    first_frame_ts: datetime
    last_frame_ts: datetime
    start_video_ms: int
    end_video_ms: int
    n_frames: int
    mask_path: str | None
    mean_area_px: float | None
    bbox_w_px: float | None
    bbox_h_px: float | None
    mean_speed_px_s: float | None
    flagged: bool
    notes: str | None
    frames: list[Frame]
    recording: Recording | None = None
    clip: Clip | None = None
