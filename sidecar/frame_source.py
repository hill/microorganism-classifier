"""Frame sources behind a single read() seam.

The capture pipeline does not care whether frames come from the EP2M over USB or
from a video file on disk. Both sources expose the same read/width/height/fps/
release surface, so the camera worker swaps one for the other based on a dev flag.

Set MICRO_DEV_VIDEO to develop without the camera plugged in:
  MICRO_DEV_VIDEO=1            replay the bundled fixture on a loop
  MICRO_DEV_VIDEO=/path.mp4    replay a file of your choosing on a loop
unset                          open the real camera device
"""

import os
import re
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations
from typing import Protocol, runtime_checkable

import av
import cv2
import numpy as np
from av.logging import Capture

from sidecar.paths import DEV_VIDEO_PATH


@runtime_checkable
class FrameSource(Protocol):
    width: int
    height: int
    fps: float

    def read(self) -> tuple[bool, np.ndarray | None]: ...

    def release(self) -> None: ...


class CameraSource:
    """Live capture through OpenCV."""

    def __init__(self, device_index: int, target_fps: float) -> None:
        backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(device_index, backend)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open camera device {device_index}")

        camera = _opencv_camera_catalog.get(device_index)
        mode = _preferred_mode(camera, target_fps) if camera else None
        if mode is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, mode.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, mode.height)
            self._cap.set(cv2.CAP_PROP_FPS, min(target_fps, mode.max_fps))

        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._cap.release()
            raise RuntimeError(f"could not read camera device {device_index}")
        self._pending: np.ndarray | None = frame
        self.width = frame.shape[1]
        self.height = frame.shape[0]
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or target_fps
        name = camera.name if camera else f"Camera {device_index}"
        print(
            f"CameraSource: opened {name} at "
            f"{self.width}x{self.height} @ {self.fps:g}fps"
        )

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._pending is not None:
            frame = self._pending
            self._pending = None
            return True, frame
        return self._cap.read()

    def release(self) -> None:
        self._cap.release()


class LoopingVideoSource:
    """Replay a video file forever, paced to real time.

    A file decodes far faster than it was filmed, so without pacing the tracker
    would see a frantic fast-forward. We sleep to hold playback near the file's
    native frame rate, and seek back to frame 0 on EOF to loop seamlessly.
    """

    def __init__(self, path: str, target_fps: float) -> None:
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open dev video {path}")
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or target_fps
        self._frame_interval = 1.0 / self.fps
        self._next_frame_at = time.monotonic()

    def read(self) -> tuple[bool, np.ndarray | None]:
        ok, frame = self._cap.read()
        if not ok:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if not ok:
                return False, None

        now = time.monotonic()
        sleep_for = self._next_frame_at - now
        if sleep_for > 0:
            time.sleep(sleep_for)
            self._next_frame_at += self._frame_interval
        else:
            # Fell behind, reset the clock so we do not spiral trying to catch up.
            self._next_frame_at = now + self._frame_interval
        return True, frame

    def release(self) -> None:
        self._cap.release()


def open_source(device_index: int, target_fps: float) -> FrameSource:
    dev = os.environ.get("MICRO_DEV_VIDEO")
    if dev:
        path = str(DEV_VIDEO_PATH) if dev in ("1", "true", "True") else dev
        print(f"FrameSource: MICRO_DEV_VIDEO={dev!r}, replaying {path} on a loop")
        return LoopingVideoSource(path, target_fps)

    return CameraSource(device_index, target_fps)


@dataclass(frozen=True, slots=True)
class _CameraMode:
    width: int
    height: int
    max_fps: float


@dataclass(frozen=True, slots=True)
class _NativeCamera:
    index: int
    name: str
    modes: tuple[_CameraMode, ...]


_opencv_camera_catalog: dict[int, _NativeCamera] = {}


_MODE_RE = re.compile(r"(\d+)x(\d+)@\[[0-9.]+\s+([0-9.]+)\]fps")


def _avfoundation_modes(device_name: str) -> tuple[_CameraMode, ...]:
    """Ask AVFoundation for the modes of one native device."""
    previous_level = av.logging.get_level()
    av.logging.set_level(av.logging.VERBOSE)
    try:
        with Capture() as logs, suppress(OSError):
            # An invalid size makes AVFoundation report every supported mode.
            av.open(
                f"{device_name}:none",
                format="avfoundation",
                options={"video_size": "123x456"},
            )
    finally:
        av.logging.set_level(previous_level)

    modes_by_size: dict[tuple[int, int], _CameraMode] = {}
    for _, _, message in logs:
        match = _MODE_RE.search(message)
        if match:
            mode = _CameraMode(
                width=int(match.group(1)),
                height=int(match.group(2)),
                max_fps=float(match.group(3)),
            )
            key = (mode.width, mode.height)
            previous = modes_by_size.get(key)
            if previous is None or mode.max_fps > previous.max_fps:
                modes_by_size[key] = mode
    return tuple(modes_by_size.values())


@lru_cache(maxsize=1)
def _native_cameras() -> tuple[_NativeCamera, ...]:
    """Return physical AVFoundation video devices and their supported sizes."""
    if sys.platform != "darwin":
        return ()
    try:
        devices = av.enumerate_input_devices("avfoundation")
    except (OSError, ValueError):
        return ()

    cameras: list[_NativeCamera] = []
    for device in devices:
        if "video" not in device.media_types:
            continue
        if device.description.startswith("Capture screen") or "Desk View" in device.description:
            continue
        try:
            index = int(device.name)
        except ValueError:
            continue
        cameras.append(
            _NativeCamera(
                index=index,
                name=device.description,
                modes=_avfoundation_modes(device.name),
            )
        )
    return tuple(cameras)


def _preferred_mode(camera: _NativeCamera, target_fps: float) -> _CameraMode | None:
    """Choose the highest resolution that remains close to the target frame rate."""
    if not camera.modes:
        return None
    smooth_modes = [mode for mode in camera.modes if mode.max_fps >= target_fps * 0.8]
    candidates = smooth_modes or list(camera.modes)
    return max(candidates, key=lambda mode: (mode.width * mode.height, mode.max_fps))


def _match_opencv_cameras(
    probed: list[tuple[int, int, int]], native: tuple[_NativeCamera, ...]
) -> dict[int, _NativeCamera]:
    """Match OpenCV indices to native devices using negotiated frame dimensions."""
    if not probed or len(native) < len(probed):
        return {}

    best_score = -1
    best_assignment: tuple[_NativeCamera, ...] | None = None
    for assignment in permutations(native, len(probed)):
        score = sum(
            1
            for (_, width, height), camera in zip(probed, assignment, strict=True)
            if any(mode.width == width and mode.height == height for mode in camera.modes)
        )
        if score > best_score:
            best_score = score
            best_assignment = assignment

    if best_assignment is None:
        return {}
    return {
        index: camera
        for (index, _, _), camera in zip(probed, best_assignment, strict=True)
    }


def probe_cameras(
    max_index: int = 4, *, refresh: bool = False
) -> list[tuple[int, str, int, int]]:
    """Probe available cameras and return index, hardware name, width, and height."""
    if sys.platform == "darwin":
        if refresh:
            _native_cameras.cache_clear()
        native = _native_cameras()[:max_index]
        probed: list[tuple[int, int, int]] = []
        for index in range(len(native)):
            cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
            try:
                if not cap.isOpened():
                    continue
                # Request a distinguishing high-resolution mode before reading.
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                ok, frame = cap.read()
                if not ok or frame is None:
                    cap.release()
                    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
                    ok, frame = cap.read()
                if ok and frame is not None:
                    probed.append((index, frame.shape[1], frame.shape[0]))
            finally:
                cap.release()

        _opencv_camera_catalog.clear()
        _opencv_camera_catalog.update(_match_opencv_cameras(probed, native))
        results: list[tuple[int, str, int, int]] = []
        for index, observed_width, observed_height in probed:
            camera = _opencv_camera_catalog.get(index)
            mode = _preferred_mode(camera, 15.0) if camera else None
            name = camera.name if camera else f"Camera {index}"
            width = mode.width if mode else observed_width
            height = mode.height if mode else observed_height
            results.append((index, name, width, height))
        return results

    results = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        try:
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
                results.append((index, f"Camera {index}", width, height))
        finally:
            cap.release()
    return results
