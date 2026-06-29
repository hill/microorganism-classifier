"""SORT tracker. Hungarian assignment between Kalman-predicted boxes and detections.

Vendored from the simple Python implementation, adapted to our Detection type.
Reference, https://arxiv.org/abs/1602.00763
"""

from dataclasses import dataclass, field

import numpy as np
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment

from sidecar.detect import Detection


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _bbox_to_z(bbox: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = bbox
    return np.array([x + w / 2, y + h / 2, w * h, w / max(h, 1)]).reshape(4, 1)


def _z_to_bbox(z: np.ndarray) -> tuple[int, int, int, int]:
    cx, cy, s, r = z[0, 0], z[1, 0], z[2, 0], z[3, 0]
    w = max(np.sqrt(max(s * r, 1e-6)), 1.0)
    h = max(s / w, 1.0)
    return int(cx - w / 2), int(cy - h / 2), int(w), int(h)


@dataclass
class TrackState:
    track_id: int
    bbox: tuple[int, int, int, int]
    last_detection: Detection
    age: int = 0
    hits: int = 0
    time_since_update: int = 0
    history: list[tuple[int, int, int, int]] = field(default_factory=list)


class _KalmanBox:
    def __init__(self, bbox: tuple[int, int, int, int]) -> None:
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = np.array(
            [
                [1, 0, 0, 0, 1, 0, 0],
                [0, 1, 0, 0, 0, 1, 0],
                [0, 0, 1, 0, 0, 0, 1],
                [0, 0, 0, 1, 0, 0, 0],
                [0, 0, 0, 0, 1, 0, 0],
                [0, 0, 0, 0, 0, 1, 0],
                [0, 0, 0, 0, 0, 0, 1],
            ],
            dtype=float,
        )
        self.kf.H = np.array(
            [
                [1, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0, 0],
                [0, 0, 1, 0, 0, 0, 0],
                [0, 0, 0, 1, 0, 0, 0],
            ],
            dtype=float,
        )
        self.kf.R[2:, 2:] *= 10.0
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        self.kf.x[:4] = _bbox_to_z(bbox)

    def predict(self) -> tuple[int, int, int, int]:
        if self.kf.x[6] + self.kf.x[2] <= 0:
            self.kf.x[6] *= 0.0
        self.kf.predict()
        return _z_to_bbox(self.kf.x[:4])

    def update(self, bbox: tuple[int, int, int, int]) -> None:
        self.kf.update(_bbox_to_z(bbox))


class SortTracker:
    def __init__(
        self,
        max_age: int = 15,
        min_hits: int = 3,
        iou_threshold: float = 0.2,
    ) -> None:
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self._next_id = 1
        self._tracks: dict[int, TrackState] = {}
        self._kalmans: dict[int, _KalmanBox] = {}

    @property
    def active_tracks(self) -> list[TrackState]:
        return [t for t in self._tracks.values() if t.hits >= self.min_hits]

    def update(self, detections: list[Detection]) -> tuple[list[TrackState], list[int]]:
        """Returns (active tracks, ids of tracks that ended this step)."""
        ended_ids: list[int] = []

        track_ids = list(self._tracks.keys())
        predicted = {tid: self._kalmans[tid].predict() for tid in track_ids}

        if track_ids and detections:
            cost = np.zeros((len(track_ids), len(detections)), dtype=float)
            for i, tid in enumerate(track_ids):
                for j, det in enumerate(detections):
                    cost[i, j] = 1.0 - _iou(predicted[tid], det.bbox)
            row_ind, col_ind = linear_sum_assignment(cost)
            assigned_tracks: set[int] = set()
            assigned_dets: set[int] = set()
            for r, c in zip(row_ind, col_ind, strict=True):
                if 1.0 - cost[r, c] >= self.iou_threshold:
                    tid = track_ids[r]
                    det = detections[c]
                    self._kalmans[tid].update(det.bbox)
                    state = self._tracks[tid]
                    state.bbox = det.bbox
                    state.last_detection = det
                    state.hits += 1
                    state.time_since_update = 0
                    state.history.append(det.bbox)
                    assigned_tracks.add(tid)
                    assigned_dets.add(c)
            unassigned_tracks = [tid for tid in track_ids if tid not in assigned_tracks]
            unassigned_dets = [j for j in range(len(detections)) if j not in assigned_dets]
        else:
            unassigned_tracks = track_ids
            unassigned_dets = list(range(len(detections)))

        for tid in unassigned_tracks:
            state = self._tracks[tid]
            state.time_since_update += 1
            state.age += 1
            if state.time_since_update > self.max_age:
                ended_ids.append(tid)

        for j in unassigned_dets:
            det = detections[j]
            tid = self._next_id
            self._next_id += 1
            self._kalmans[tid] = _KalmanBox(det.bbox)
            self._tracks[tid] = TrackState(
                track_id=tid,
                bbox=det.bbox,
                last_detection=det,
                hits=1,
                history=[det.bbox],
            )

        for tid in ended_ids:
            self._tracks.pop(tid, None)
            self._kalmans.pop(tid, None)

        return self.active_tracks, ended_ids

    def all_known_tracks(self) -> dict[int, TrackState]:
        return dict(self._tracks)
