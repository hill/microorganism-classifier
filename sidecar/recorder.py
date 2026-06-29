"""Continuous MP4 recorder using PyAV.

Writes raw frames to disk as the source of truth. Resilient to slow consumers
by dropping frames if the queue saturates rather than blocking capture.
"""

import queue
import threading
from fractions import Fraction
from pathlib import Path

import av
import numpy as np


class RawRecorder:
    def __init__(
        self,
        path: Path,
        width: int,
        height: int,
        fps: float,
        max_queue: int = 64,
    ) -> None:
        self.path = path
        self.width = width
        self.height = height
        self.fps = fps
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=max_queue)
        self._thread: threading.Thread | None = None
        self._frames_written = 0
        self._dropped = 0

    @property
    def frames_written(self) -> int:
        return self._frames_written

    @property
    def dropped(self) -> int:
        return self._dropped

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._queue.put(None)
        self._thread.join(timeout=10.0)
        self._thread = None

    def push(self, frame_bgr: np.ndarray) -> None:
        try:
            self._queue.put_nowait(frame_bgr)
        except queue.Full:
            self._dropped += 1

    def _run(self) -> None:
        container = av.open(str(self.path), mode="w")
        try:
            stream = container.add_stream("h264", rate=Fraction(int(self.fps), 1))
            stream.width = self.width
            stream.height = self.height
            stream.pix_fmt = "yuv420p"
            stream.options = {"preset": "veryfast", "crf": "23"}

            while True:
                frame_bgr = self._queue.get()
                if frame_bgr is None:
                    break
                vframe = av.VideoFrame.from_ndarray(frame_bgr, format="bgr24")
                for packet in stream.encode(vframe):
                    container.mux(packet)
                self._frames_written += 1

            for packet in stream.encode():
                container.mux(packet)
        finally:
            container.close()
