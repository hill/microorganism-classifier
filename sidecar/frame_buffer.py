"""Rolling in-memory JPEG buffer.

Stores the most recent N seconds of encoded frames so that a clip can be saved
retrospectively without having to write the full live stream to disk.
"""

import threading
from collections import deque
from dataclasses import dataclass


@dataclass(slots=True)
class BufferedFrame:
    monotonic_ts: float
    jpeg: bytes


class JpegBuffer:
    def __init__(self, max_seconds: float, fps: float) -> None:
        self.max_seconds = max_seconds
        capacity = max(1, int(max_seconds * fps * 1.5))
        self._frames: deque[BufferedFrame] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def push(self, monotonic_ts: float, jpeg: bytes) -> None:
        with self._lock:
            self._frames.append(BufferedFrame(monotonic_ts, jpeg))

    def snapshot_since(self, monotonic_ts: float) -> list[BufferedFrame]:
        """Return a copy of all buffered frames with ts >= the cutoff."""
        with self._lock:
            return [f for f in self._frames if f.monotonic_ts >= monotonic_ts]

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
