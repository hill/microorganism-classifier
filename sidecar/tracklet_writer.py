"""Accumulates per-track frames in memory, writes the best K on track end.

Each active SORT track gets a buffer. When SORT reports a track ended, we pick
the K sharpest frames, save crops plus the mask of the sharpest, compute
morphometrics, and update the DB row.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.engine import Engine
from sqlmodel import Session as DbSession

from sidecar.detect import Detection
from sidecar.models import Frame, Track
from sidecar.morphometry import TrackletMetrics, sharpness, summarise
from sidecar.track import TrackState

TOP_K_FRAMES = 5
CROP_PAD = 20


@dataclass
class _Buffer:
    db_track_id: int
    run_id: int
    started_at: datetime
    start_video_ms: int
    history: list[tuple[int, int, int, int]] = field(default_factory=list)
    areas: list[float] = field(default_factory=list)
    candidate_crops: list[tuple[float, np.ndarray, np.ndarray, datetime]] = field(
        default_factory=list
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _crop(frame: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    h, w = frame.shape[:2]
    x, y, bw, bh = bbox
    x1 = max(0, x - CROP_PAD)
    y1 = max(0, y - CROP_PAD)
    x2 = min(w, x + bw + CROP_PAD)
    y2 = min(h, y + bh + CROP_PAD)
    return frame[y1:y2, x1:x2].copy()


class TrackletWriter:
    def __init__(
        self,
        engine: Engine,
        run_id: int,
        fps: float,
        run_dir: Path,
    ) -> None:
        self.engine = engine
        self.run_id = run_id
        self.fps = fps
        self.run_dir = run_dir
        self.tracks_dir = run_dir / "tracks"
        self.tracks_dir.mkdir(parents=True, exist_ok=True)
        self._buffers: dict[int, _Buffer] = {}
        self._sort_to_db: dict[int, int] = {}
        self._frame_count = 0

    @property
    def sort_to_db(self) -> dict[int, int]:
        return self._sort_to_db

    def step(
        self,
        frame: np.ndarray,
        active: list[TrackState],
        ended: list[int],
        video_ms: int,
    ) -> None:
        self._frame_count += 1
        now = _utc_now()

        with DbSession(self.engine) as session:
            for state in active:
                sort_id = state.track_id
                db_id = self._sort_to_db.get(sort_id)
                if db_id is None:
                    db_id = self._insert_track_row(session, now, video_ms)
                    self._sort_to_db[sort_id] = db_id
                    self._buffers[db_id] = _Buffer(
                        db_track_id=db_id,
                        run_id=self.run_id,
                        started_at=now,
                        start_video_ms=video_ms,
                    )

                buf = self._buffers[db_id]
                det: Detection = state.last_detection
                buf.history.append(state.bbox)
                buf.areas.append(det.area_px)

                crop = _crop(frame, state.bbox)
                sharp = sharpness(crop) if crop.size else 0.0
                buf.candidate_crops.append((sharp, crop, det.mask, now))
                if len(buf.candidate_crops) > TOP_K_FRAMES * 3:
                    buf.candidate_crops.sort(key=lambda t: t[0], reverse=True)
                    buf.candidate_crops = buf.candidate_crops[: TOP_K_FRAMES * 2]

                self._update_track_row(session, db_id, now, video_ms, len(buf.history))

            session.commit()

        for sort_id in ended:
            db_id = self._sort_to_db.pop(sort_id, None)
            if db_id is None:
                continue
            buf = self._buffers.pop(db_id, None)
            if buf is None:
                continue
            self._finalise(buf, video_ms)

    def flush_all(self, video_ms: int) -> None:
        for sort_id in list(self._sort_to_db.keys()):
            db_id = self._sort_to_db.pop(sort_id)
            buf = self._buffers.pop(db_id, None)
            if buf is not None:
                self._finalise(buf, video_ms)

    def _insert_track_row(self, session: DbSession, now: datetime, video_ms: int) -> int:
        track = Track(
            run_id=self.run_id,
            first_frame_ts=now,
            last_frame_ts=now,
            start_video_ms=video_ms,
            end_video_ms=video_ms,
            n_frames=1,
        )
        session.add(track)
        session.flush()
        return track.id

    def _update_track_row(
        self,
        session: DbSession,
        db_id: int,
        now: datetime,
        video_ms: int,
        n_frames: int,
    ) -> None:
        track = session.get(Track, db_id)
        if track is None:
            return
        track.last_frame_ts = now
        track.end_video_ms = video_ms
        track.n_frames = n_frames
        session.add(track)

    def _finalise(self, buf: _Buffer, end_video_ms: int) -> None:
        track_dir = self.tracks_dir / f"track_{buf.db_track_id:06d}"
        track_dir.mkdir(parents=True, exist_ok=True)

        metrics: TrackletMetrics = summarise(buf.history, buf.areas, self.fps)

        buf.candidate_crops.sort(key=lambda t: t[0], reverse=True)
        top = buf.candidate_crops[:TOP_K_FRAMES]

        frame_records: list[tuple[datetime, str, float]] = []
        for i, (sharp, crop, _mask, ts) in enumerate(top, 1):
            path = track_dir / f"frame_{i:03d}.png"
            cv2.imwrite(str(path), crop)
            frame_records.append((ts, str(path), float(sharp)))

        mask_path: str | None = None
        if top:
            best_mask = top[0][2]
            mask_file = track_dir / "mask.png"
            cv2.imwrite(str(mask_file), best_mask)
            mask_path = str(mask_file)

        with DbSession(self.engine) as session:
            track = session.get(Track, buf.db_track_id)
            if track is not None:
                track.end_video_ms = end_video_ms
                track.n_frames = len(buf.history)
                track.mask_path = mask_path
                track.mean_area_px = metrics.mean_area_px
                track.bbox_w_px = metrics.bbox_w_px
                track.bbox_h_px = metrics.bbox_h_px
                track.mean_speed_px_s = metrics.mean_speed_px_s
                session.add(track)

            for ts, path, sharp in frame_records:
                session.add(Frame(track_id=buf.db_track_id, ts=ts, path=path, sharpness=sharp))

            session.commit()
