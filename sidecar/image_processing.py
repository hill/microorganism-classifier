"""Live image adjustments applied to every captured frame.

A single ImageProcessor instance is shared between the API thread (which
updates parameters from the UI) and the capture loop (which applies them).
The parameter struct is replaced atomically on each update so no lock is
needed for reads.
"""

from dataclasses import dataclass, replace

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class ProcessingParams:
    brightness: int = 0
    contrast: float = 1.0
    gamma: float = 1.0
    wb_r: float = 1.0
    wb_g: float = 1.0
    wb_b: float = 1.0
    invert: bool = False
    local_contrast: float = 0.0
    sharpness: float = 0.0
    grayscale: bool = False

    def is_identity(self) -> bool:
        return (
            self.brightness == 0
            and self.contrast == 1.0
            and self.gamma == 1.0
            and self.wb_r == 1.0
            and self.wb_g == 1.0
            and self.wb_b == 1.0
            and not self.invert
            and self.local_contrast == 0.0
            and self.sharpness == 0.0
            and not self.grayscale
        )


def _build_lut(p: ProcessingParams) -> np.ndarray:
    """Pre-bake brightness, contrast, gamma and white-balance into per-channel 8-bit LUTs.

    Returns array of shape (3, 256) for BGR.
    """
    x = np.arange(256, dtype=np.float32)
    # brightness + contrast around midpoint
    v = (x - 128.0) * p.contrast + 128.0 + float(p.brightness)
    np.clip(v, 0.0, 255.0, out=v)
    # gamma
    if p.gamma != 1.0:
        v = np.power(v / 255.0, 1.0 / p.gamma) * 255.0
        np.clip(v, 0.0, 255.0, out=v)
    # per-channel white-balance gain (frame is BGR)
    lut_b = np.clip(v * p.wb_b, 0, 255).astype(np.uint8)
    lut_g = np.clip(v * p.wb_g, 0, 255).astype(np.uint8)
    lut_r = np.clip(v * p.wb_r, 0, 255).astype(np.uint8)
    if p.invert:
        lut_b = 255 - lut_b
        lut_g = 255 - lut_g
        lut_r = 255 - lut_r
    return np.stack([lut_b, lut_g, lut_r], axis=0)


class ImageProcessor:
    def __init__(self, params: ProcessingParams | None = None) -> None:
        self._params = params or ProcessingParams()
        self._lut: np.ndarray | None = None
        self._lut_for: ProcessingParams | None = None
        self._clahe: cv2.CLAHE | None = None
        self._clahe_limit: float | None = None

    @property
    def params(self) -> ProcessingParams:
        return self._params

    def update(self, **changes) -> ProcessingParams:
        self._params = replace(self._params, **changes)
        return self._params

    def set(self, params: ProcessingParams) -> None:
        self._params = params

    def apply(self, frame: np.ndarray) -> np.ndarray:
        p = self._params
        if p.is_identity():
            return frame
        if self._lut is None or self._lut_for != p:
            self._lut = _build_lut(p)
            self._lut_for = p
        lut = self._lut
        b, g, r = cv2.split(frame)
        b = cv2.LUT(b, lut[0])
        g = cv2.LUT(g, lut[1])
        r = cv2.LUT(r, lut[2])
        result = cv2.merge([b, g, r])

        if p.grayscale:
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        if p.local_contrast > 0:
            if self._clahe is None or self._clahe_limit != p.local_contrast:
                self._clahe = cv2.createCLAHE(
                    clipLimit=max(0.25, p.local_contrast),
                    tileGridSize=(8, 8),
                )
                self._clahe_limit = p.local_contrast
            lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
            lightness, channel_a, channel_b = cv2.split(lab)
            lightness = self._clahe.apply(lightness)
            result = cv2.cvtColor(
                cv2.merge([lightness, channel_a, channel_b]),
                cv2.COLOR_LAB2BGR,
            )

        if p.sharpness > 0:
            blurred = cv2.GaussianBlur(result, (0, 0), sigmaX=1.2, sigmaY=1.2)
            result = cv2.addWeighted(result, 1.0 + p.sharpness, blurred, -p.sharpness, 0)

        return result
