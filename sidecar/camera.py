"""Camera worker. Owns the frame source and runs the live pipeline.

The source streams continuously from app start, so there is always a live
preview. Clip recording and live detection can be enabled independently.
Clips include the most recent N seconds from a rolling JPEG buffer plus all
frames captured between clip start and clip stop. Stopping a clip leaves the
preview and optional live detection running.
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
from sidecar.models import Clip, Run
from sidecar.settings_service import processor as get_processor
from sidecar.track import SortTracker

RETRY_DELAY_S = 1.0
BUFFER_SECONDS = 60.0
BUFFER_JPEG_QUALITY = 70


@dataclass
class PreviewState:
    frame: np.ndarray | None = None
    tracks: list[dict] = field(default_factory=list)
    frame_index: int = 0
    saved_tracks: int = 0


@dataclass(frozen=True, slots=True)
class DetectionCapture:
    track_id: int
    frame: np.ndarray
    bbox: tuple[int, int, int, int]
    area_px: float
    hits: int
    history: tuple[tuple[int, int, int, int], ...]


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
    start_wall: float


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
        self._detection_lock = threading.Lock()
        self._detection_enabled = False
        self._detector: Detector | None = None
        self._tracker: SortTracker | None = None
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

    @property
    def detection_enabled(self) -> bool:
        with self._detection_lock:
            return self._detection_enabled

    def set_detection_enabled(self, enabled: bool) -> None:
        with self._detection_lock:
            self._detection_enabled = enabled
            if enabled:
                self._detector = Detector()
                self._tracker = SortTracker()
            else:
                self._detector = None
                self._tracker = None
        if not enabled:
            with self._state_lock:
                self._state.tracks = []

    def capture_detection(self, track_id: int) -> DetectionCapture | None:
        with self._detection_lock:
            if self._tracker is None:
                return None
            state = self._tracker.all_known_tracks().get(track_id)
            if state is None:
                return None
            bbox = state.bbox
            area_px = state.last_detection.area_px
            hits = state.hits
            history = tuple(state.history)
            with self._state_lock:
                if self._state.frame is None:
                    return None
                frame = _crop_detection(self._state.frame, bbox)
        return DetectionCapture(
            track_id=track_id,
            frame=frame,
            bbox=bbox,
            area_px=area_px,
            hits=hits,
            history=history,
        )

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
                start_wall=time.monotonic(),
            )

    def stop_clip(self) -> None:
        with self._clip_lock:
            ctx = self._clip_ctx
            self._clip_ctx = None
        if ctx is None:
            return

        ctx.writer.stop()

        video_ms = int((time.monotonic() - ctx.start_wall) * 1000)
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
        """Write an active clip and independently update optional live detection."""
        with self._clip_lock:
            ctx = self._clip_ctx
            if ctx is not None:
                ctx.writer.push(frame)

        with self._detection_lock:
            if not self._detection_enabled or self._detector is None or self._tracker is None:
                return [], 0
            detections = self._detector.process(frame)
            active, _ = self._tracker.update(detections)
            preview_tracks: list[dict] = []
            for state in active:
                x, y, w, h = state.bbox
                preview_tracks.append(
                    {
                        "id": state.track_id,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "label": None,
                        "n_frames": state.hits,
                    }
                )
            return preview_tracks, 0


def _crop_detection(
    frame: np.ndarray, bbox: tuple[int, int, int, int], padding: int = 20
) -> np.ndarray:
    height, width = frame.shape[:2]
    x, y, box_width, box_height = bbox
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(width, x + box_width + padding)
    y2 = min(height, y + box_height + padding)
    return frame[y1:y2, x1:x2].copy()
