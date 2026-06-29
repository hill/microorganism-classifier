"""Background subtraction + contour extraction.

A still microscope stage means MOG2 background subtraction works well.
The blurry edges of out-of-focus debris are filtered by a minimum area threshold.
"""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class Detection:
    bbox: tuple[int, int, int, int]  # x, y, w, h
    area_px: float
    mask: np.ndarray  # binary mask of the detection, same shape as full frame


class Detector:
    def __init__(
        self,
        min_area_px: float = 200.0,
        max_area_px: float = 200_000.0,
        history: int = 200,
        var_threshold: float = 25.0,
        detect_shadows: bool = False,
    ) -> None:
        self.min_area = min_area_px
        self.max_area = max_area_px
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=detect_shadows,
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    def process(self, frame: np.ndarray) -> list[Detection]:
        fg = self._subtractor.apply(frame)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self._kernel)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, self._kernel)

        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections: list[Detection] = []
        for c in contours:
            area = float(cv2.contourArea(c))
            if area < self.min_area or area > self.max_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask, [c], -1, 255, thickness=cv2.FILLED)
            detections.append(Detection(bbox=(x, y, w, h), area_px=area, mask=mask))

        return detections
