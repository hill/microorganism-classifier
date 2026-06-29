"""Per-tracklet morphometric features in pixel units."""

import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class TrackletMetrics:
    mean_area_px: float
    bbox_w_px: float
    bbox_h_px: float
    mean_speed_px_s: float


def sharpness(image: np.ndarray) -> float:
    """Variance of Laplacian. Higher means sharper."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def summarise(
    history: list[tuple[int, int, int, int]],
    areas: list[float],
    fps: float,
) -> TrackletMetrics:
    if not history:
        return TrackletMetrics(0.0, 0.0, 0.0, 0.0)

    mean_w = float(np.mean([h[2] for h in history]))
    mean_h = float(np.mean([h[3] for h in history]))
    mean_area = float(np.mean(areas)) if areas else 0.0

    distances: list[float] = []
    for prev, curr in zip(history[:-1], history[1:], strict=True):
        pcx, pcy = prev[0] + prev[2] / 2, prev[1] + prev[3] / 2
        ccx, ccy = curr[0] + curr[2] / 2, curr[1] + curr[3] / 2
        distances.append(math.hypot(ccx - pcx, ccy - pcy))
    total = sum(distances)
    seconds = max(len(history) - 1, 1) / fps
    speed = total / seconds if seconds > 0 else 0.0

    return TrackletMetrics(
        mean_area_px=mean_area,
        bbox_w_px=mean_w,
        bbox_h_px=mean_h,
        mean_speed_px_s=speed,
    )
