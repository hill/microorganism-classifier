"""MP4 writer for a clip, fed from a JPEG buffer plus live frames.

The writer owns its own thread so the capture loop is never blocked by encode.
"""

import queue
import threading
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

from sidecar.frame_buffer import BufferedFrame


class ClipWriter:
    def __init__(
        self,
        path: Path,
        width: int,
        height: int,
        fps: float,
        max_queue: int = 256,
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
        self._thread.join(timeout=15.0)
        self._thread = None

    def prime_from_buffer(self, frames: list[BufferedFrame]) -> None:
        """Decode JPEGs from the rolling buffer and enqueue them as the head of the clip."""
        for f in frames:
            arr = np.frombuffer(f.jpeg, dtype=np.uint8)
            decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if decoded is None:
                continue
            self._enqueue(decoded)

    def push(self, frame_bgr: np.ndarray) -> None:
        self._enqueue(frame_bgr)

    def _enqueue(self, frame: np.ndarray) -> None:
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            self._dropped += 1

    def _run(self) -> None:
        container = av.open(str(self.path), mode="w")
        try:
            stream = container.add_stream("h264", rate=Fraction(int(self.fps), 1))
            stream.width = self.width
            stream.height = self.height
            stream.pix_fmt = "yuv420p"
            stream.options = {"preset": "veryfast", "crf": "20"}

            while True:
                frame_bgr = self._queue.get()
                if frame_bgr is None:
                    break
                if frame_bgr.shape[1] != self.width or frame_bgr.shape[0] != self.height:
                    frame_bgr = cv2.resize(frame_bgr, (self.width, self.height))
                vframe = av.VideoFrame.from_ndarray(frame_bgr, format="bgr24")
                for packet in stream.encode(vframe):
                    container.mux(packet)
                self._frames_written += 1

            for packet in stream.encode():
                container.mux(packet)
        finally:
            container.close()
