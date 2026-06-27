"""Image binarization strategies for the SVG converter.

Split out of svg_converter.py to keep files under the 300-line target.

Three modes:
  "otsu"     — global Otsu threshold (best for clean line art on uniform bg).
  "adaptive" — adaptive local threshold (robust to gradients / uneven lighting).
  "auto"     — pick per-image: Otsu for evenly-lit frames, adaptive otherwise.
"""

from __future__ import annotations

import numpy as np

try:
    import cv2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - local environments may omit OpenCV
    cv2 = None


def otsu_binary(blurred: np.ndarray) -> np.ndarray:
    """Global Otsu threshold (best for clean line art on a uniform background)."""
    if cv2 is None:  # pragma: no cover - matches svg_converter guard
        raise RuntimeError("OpenCV is not installed")
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def adaptive_binary(blurred: np.ndarray) -> np.ndarray:
    """Adaptive (local) threshold — robust to gradients and uneven lighting.

    AI-generated images often have soft shading and non-uniform backgrounds
    where a single global threshold drops bright strokes or floods dark areas.
    A local threshold decides per-neighborhood, preserving thin strokes.
    """
    if cv2 is None:  # pragma: no cover - matches svg_converter guard
        raise RuntimeError("OpenCV is not installed")
    return cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=31,
        C=7,
    )


def is_uneven(gray: np.ndarray) -> bool:
    """Heuristic: does the image have uneven lighting / shading?

    Splits the frame into quadrants and compares their mean intensity. A wide
    spread between the brightest and darkest quadrant means a global threshold
    would misbehave, so adaptive thresholding should be preferred.
    """
    h, w = gray.shape
    if h < 4 or w < 4:
        return False
    mh, mw = h // 2, w // 2
    quadrant_means = [
        float(gray[:mh, :mw].mean()),
        float(gray[:mh, mw:].mean()),
        float(gray[mh:, :mw].mean()),
        float(gray[mh:, mw:].mean()),
    ]
    return (max(quadrant_means) - min(quadrant_means)) > 40.0


def binarize(gray: np.ndarray, blurred: np.ndarray, threshold_mode: str) -> tuple[np.ndarray, str]:
    """Pick a binarization strategy and return (binary, method name).

    Raises:
        ValueError: when threshold_mode is not one of otsu/adaptive/auto.
    """
    if threshold_mode == "otsu":
        return otsu_binary(blurred), "otsu"
    if threshold_mode == "adaptive":
        return adaptive_binary(blurred), "adaptive"
    if threshold_mode == "auto":
        if is_uneven(gray):
            return adaptive_binary(blurred), "adaptive"
        return otsu_binary(blurred), "otsu"
    raise ValueError(f"unknown threshold_mode: {threshold_mode!r}")
