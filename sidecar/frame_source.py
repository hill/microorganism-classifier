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
import sys
import time
from typing import Protocol, runtime_checkable

import av
import cv2
import numpy as np

from sidecar.paths import DEV_VIDEO_PATH


@runtime_checkable
class FrameSource(Protocol):
    width: int
    height: int
    fps: float

    def read(self) -> tuple[bool, np.ndarray | None]: ...

    def release(self) -> None: ...


class CameraSource:
    """Live capture from a device index. A thin pass-through over VideoCapture."""

    def __init__(self, device_index: int, target_fps: float) -> None:
        self._cap = _open_camera(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open camera device {device_index}")
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or target_fps
        print(
            f"CameraSource: opened device {device_index} at "
            f"{self.width}x{self.height} @ {self.fps:.0f}fps"
        )

    def read(self) -> tuple[bool, np.ndarray | None]:
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


def _open_camera(device_index: int) -> cv2.VideoCapture:
    """Open a camera with the backend used to derive its hardware name."""
    if sys.platform == "darwin":
        return cv2.VideoCapture(device_index, cv2.CAP_AVFOUNDATION)
    return cv2.VideoCapture(device_index)


def camera_names() -> dict[int, str]:
    """Return native hardware names keyed by the OpenCV device index."""
    if sys.platform != "darwin":
        return {}
    try:
        devices = av.enumerate_input_devices("avfoundation")
    except (OSError, ValueError):
        return {}

    names: dict[int, str] = {}
    for device in devices:
        if "video" not in device.media_types or device.description.startswith("Capture screen"):
            continue
        try:
            index = int(device.name)
        except ValueError:
            continue
        names[index] = device.description
    return names


def probe_cameras(max_index: int = 4) -> list[tuple[int, str, int, int]]:
    """Probe available cameras and return index, hardware name, width, and height."""
    names = camera_names()
    indices = sorted(names) if names else list(range(max_index))
    results: list[tuple[int, str, int, int]] = []
    for i in indices[:max_index]:
        cap = _open_camera(i)
        try:
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
                results.append((i, names.get(i, f"Camera {i}"), w, h))
        finally:
            cap.release()
    return results
