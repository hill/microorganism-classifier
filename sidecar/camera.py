"""Camera worker. Owns the frame source and runs the live pipeline.

The source streams continuously from app start, so there is always a live
preview. A clip layers detection plus on-disk save on top of that stream,
saving the most recent N seconds from a rolling JPEG buffer plus all frames
captured between clip start and clip stop. Stopping the clip leaves the
preview running so the user can immediately start another clip.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.engine import Engine

from sidecar.clip_writer import ClipWriter
from sidecar.db import session_scope
from sidecar.detect import Detector
from sidecar.frame_buffer import JpegBuffer
from sidecar.frame_source import open_source
from sidecar.image_processing import ImageProcessor
from sidecar.models import Clip, Run, Track
from sidecar.settings_service import processor as get_processor
from sidecar.track import SortTracker
from sidecar.tracklet_writer import TrackletWriter

RETRY_DELAY_S = 1.0
BUFFER_SECONDS = 60.0
BUFFER_JPEG_QUALITY = 70


@dataclass
class PreviewState:
    frame: np.ndarray | None = None
    tracks: list[dict] = field(default_factory=list)
    frame_index: int = 0
    saved_tracks: int = 0


@dataclass
class ClipConfig:
    clip_id: int
    run_id: int
    clip_dir: Path
    clip_path: Path
    seconds_before: float


@dataclass
class _ClipContext:
    """Everything that exists only while a clip is being recorded."""

    config: ClipConfig
    writer: ClipWriter
    tracklet_writer: TrackletWriter
    detector: Detector
    tracker: SortTracker
    start_wall: float
    saved_tracks: int = 0


class CameraWorker:
    def __init__(self, engine: Engine, target_fps: float = 15.0) -> None:
        self.engine = engine
        self._target_fps = target_fps
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._reload_event = threading.Event()
        self._state_lock = threading.Lock()
        self._state = PreviewState()
        self._clip_lock = threading.Lock()
        self._clip_ctx: _ClipContext | None = None
        self._labels: dict[int, str] = {}
        self._source_dims: tuple[int, int, float] | None = None
        self._buffer = JpegBuffer(BUFFER_SECONDS, target_fps)

    def request_reload(self) -> None:
        """Signal the capture loop to drop the current source and re-open."""
        self._reload_event.set()

    @property
    def is_capturing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_clipping(self) -> bool:
        return self._clip_ctx is not None

    @property
    def current_clip(self) -> ClipConfig | None:
        ctx = self._clip_ctx
        return ctx.config if ctx is not None else None

    def snapshot(self) -> PreviewState:
        with self._state_lock:
            if self._state.frame is None:
                return PreviewState(frame=None, tracks=list(self._state.tracks))
            return PreviewState(
                frame=self._state.frame.copy(),
                tracks=list(self._state.tracks),
                frame_index=self._state.frame_index,
                saved_tracks=self._state.saved_tracks,
            )

    def set_label(self, db_track_id: int, label: str) -> None:
        self._labels[db_track_id] = label
        with session_scope() as session:
            track = session.get(Track, db_track_id)
            if track is not None:
                track.label = label
                session.add(track)

    def start_capture(self) -> None:
        if self.is_capturing:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self.is_clipping:
            self.stop_clip()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        self._thread = None

    def start_clip(self, config: ClipConfig) -> None:
        with self._clip_lock:
            if self._clip_ctx is not None:
                raise RuntimeError("a clip is already being recorded")
            if self._source_dims is None:
                raise RuntimeError("camera not ready yet")
            width, height, fps = self._source_dims

            writer = ClipWriter(config.clip_path, width, height, fps)
            writer.start()

            cutoff = time.monotonic() - config.seconds_before
            buffered = self._buffer.snapshot_since(cutoff)
            writer.prime_from_buffer(buffered)

            self._clip_ctx = _ClipContext(
                config=config,
                writer=writer,
                tracklet_writer=TrackletWriter(self.engine, config.run_id, fps, config.clip_dir),
                detector=Detector(),
                tracker=SortTracker(),
                start_wall=time.monotonic(),
            )

    def stop_clip(self) -> None:
        with self._clip_lock:
            ctx = self._clip_ctx
            self._clip_ctx = None
        if ctx is None:
            return

        video_ms = int((time.monotonic() - ctx.start_wall) * 1000)
        ctx.tracklet_writer.flush_all(video_ms)
        ctx.writer.stop()

        duration_ms = video_ms + int(ctx.config.seconds_before * 1000)
        ended = datetime.now(UTC)
        with session_scope() as session:
            clip = session.get(Clip, ctx.config.clip_id)
            if clip is not None:
                clip.duration_ms = duration_ms
                clip.ended_at = ended
                session.add(clip)
            run = session.get(Run, ctx.config.run_id)
            if run is not None:
                run.ended_at = ended
                session.add(run)

    def _capture_loop(self) -> None:
        from sidecar.settings_service import get_settings

        frame_index = 0
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), BUFFER_JPEG_QUALITY]
        image_processor: ImageProcessor = get_processor()
        while not self._stop_event.is_set():
            device_index = get_settings().device_index
            try:
                source = open_source(device_index, self._target_fps)
            except RuntimeError as err:
                print(f"CameraWorker: {err}, retrying in {RETRY_DELAY_S:.0f}s")
                self._stop_event.wait(RETRY_DELAY_S)
                continue

            self._source_dims = (source.width, source.height, source.fps)
            self._reload_event.clear()
            try:
                while not self._stop_event.is_set() and not self._reload_event.is_set():
                    ok, frame = source.read()
                    if not ok or frame is None:
                        break

                    # Apply user-configured adjustments to every downstream consumer.
                    frame = image_processor.apply(frame)

                    ts = time.monotonic()
                    ok_enc, jpeg = cv2.imencode(".jpg", frame, encode_params)
                    if ok_enc:
                        self._buffer.push(ts, bytes(jpeg))

                    preview_tracks, saved = self._process_frame(frame)
                    with self._state_lock:
                        self._state = PreviewState(
                            frame=frame,
                            tracks=preview_tracks,
                            frame_index=frame_index,
                            saved_tracks=saved,
                        )
                    frame_index += 1
            finally:
                source.release()
                self._source_dims = None

    def _process_frame(self, frame: np.ndarray) -> tuple[list[dict], int]:
        """Run detection plus clip-writing if a clip is active, else pass through."""
        with self._clip_lock:
            ctx = self._clip_ctx
            if ctx is None:
                return [], 0

            video_ms = int((time.monotonic() - ctx.start_wall) * 1000)
            ctx.writer.push(frame)
            detections = ctx.detector.process(frame)
            active, ended = ctx.tracker.update(detections)
            ctx.tracklet_writer.step(frame, active, ended, video_ms)
            ctx.saved_tracks += len(ended)

            preview_tracks = []
            for state in active:
                db_id = ctx.tracklet_writer.sort_to_db.get(state.track_id)
                if db_id is None:
                    continue
                x, y, w, h = state.bbox
                preview_tracks.append(
                    {
                        "id": db_id,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "label": self._labels.get(db_id),
                        "n_frames": state.hits,
                    }
                )
            return preview_tracks, ctx.saved_tracks
