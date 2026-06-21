"""图像转 SVG 路径转换器 - OpenCV 矢量化

改造记录（2026-06-22）：新增骨架化链路，使绘图机输出单笔开放路径而非双线闭合轮廓。
"""

from io import BytesIO
import logging
from typing import Any

import httpx
import numpy as np
from PIL import Image

try:
    import cv2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - local environments may omit OpenCV
    cv2 = None

from xiaozhi_drawing.skeleton_tracer import polylines_to_svg_paths, trace_skeleton_polylines

logger = logging.getLogger(__name__)


# ── 图像下载 ───────────────────────────────────────────────────────────────────

async def _download_image(image_url: str) -> BytesIO:
    """Download image from URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        return BytesIO(resp.content)


# ── 图像预处理 ─────────────────────────────────────────────────────────────────

def _preprocess_image(image_data: BytesIO) -> tuple:
    """Load, resize, gray, blur, and Otsu-threshold the image."""
    if cv2 is None:
        raise RuntimeError("OpenCV is not installed")
    img = Image.open(image_data).convert("RGB")
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return gray, binary


# ── 骨架化 ─────────────────────────────────────────────────────────────────────

def _thin_morphological(binary: np.ndarray) -> np.ndarray:
    """Pure-OpenCV iterative morphological thinning fallback.

    Iteratively erodes blobs toward their centerline until convergence (≤50 passes).
    """
    if cv2 is None:  # pragma: no cover
        logger.warning("OpenCV not installed; skeletonize disabled, returning input as-is")
        return binary
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    thinned = binary.copy()
    for _ in range(50):
        prev = thinned.copy()
        eroded = cv2.erode(thinned, kernel)
        diff = cv2.subtract(thinned, cv2.dilate(eroded, kernel))
        thinned = cv2.bitwise_or(eroded, diff)
        if cv2.countNonZero(cv2.subtract(prev, thinned)) == 0:
            break
    return thinned


def _thin_binary(binary: np.ndarray) -> tuple[np.ndarray, str]:
    """Thin binary image to a single-pixel-wide skeleton.

    Degradation chain (no silent failure):
      skimage.morphology.skeletonize  →  cv2.ximgproc.thinning  →  _thin_morphological

    Returns:
        (thinned array, method name: skimage | ximgproc | morphological)
    """
    try:
        from skimage.morphology import skeletonize as sk_thin  # type: ignore[import-not-found]

        return (sk_thin(binary > 0) * 255).astype(np.uint8), "skimage"
    except Exception as exc:
        logger.debug("skimage skeletonize unavailable (%s); trying cv2.ximgproc.thinning", type(exc).__name__)
    if cv2 is not None:
        try:
            return cv2.ximgproc.thinning(binary), "ximgproc"
        except Exception as exc:
            logger.debug("cv2.ximgproc.thinning unavailable (%s); using morphological fallback", type(exc).__name__)
    logger.info("Using morphological thinning fallback for skeletonization")
    return _thin_morphological(binary), "morphological"


# ── 路径提取 ───────────────────────────────────────────────────────────────────

def _contour_to_svg_path(contour: np.ndarray, *, closed: bool = True) -> str:
    """Convert an OpenCV contour to SVG path string.

    Args:
        contour: OpenCV contour array (N, 1, 2).
        closed: True → append Z (outline/fill mode).
                False → open path (single-stroke pen-plotter mode, no Z).
    """
    points = contour.reshape(-1, 2)
    if len(points) == 0:
        return ""
    parts = [f"M {points[0][0]} {points[0][1]}"]
    for x, y in points[1:]:
        parts.append(f"L {x} {y}")
    if closed:
        parts.append("Z")
    return " ".join(parts)


def _extract_svg_paths(
    binary: np.ndarray,
    simplify_epsilon: float,
    min_contour_area: int,
    *,
    skeletonize: bool = False,
) -> tuple[list[str], str | None]:
    """Find contours, filter, simplify, and convert to SVG paths.

    skeletonize=True (pen-plotter mode): thin binary to single-pixel skeleton first
    so each stroke becomes one open path without Z — prevents the drawing machine
    from retracing the same line as a double-edge closed outline.

    skeletonize=False (legacy mode): original RETR_EXTERNAL + closed-path behavior,
    fully backward-compatible.
    """
    if cv2 is None:
        raise RuntimeError("OpenCV is not installed")
    svg_paths: list[str] = []
    thinning_method: str | None = None
    if skeletonize:
        src, thinning_method = _thin_binary(binary)
        polylines = trace_skeleton_polylines(src)
        svg_paths = polylines_to_svg_paths(
            polylines,
            simplify_epsilon=simplify_epsilon,
            min_arc_length=simplify_epsilon * 2,
        )
    else:
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if cv2.contourArea(contour) < min_contour_area:
                continue
            approx = cv2.approxPolyDP(contour, simplify_epsilon, True)
            if len(approx) >= 3:
                path = _contour_to_svg_path(approx, closed=True)
                if path:
                    svg_paths.append(path)
    return svg_paths, thinning_method


def _legacy_fallback_path(width: int, height: int) -> str:
    return f"M 0 0 L {width} 0 L {width} {height} L 0 {height} Z"


def _svg_payload(
    status: str,
    *,
    svg_paths: list[str] | None = None,
    width: int = 0,
    height: int = 0,
    skeletonize: bool = False,
    thinning_method: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    paths = svg_paths or []
    return {
        "status": status,
        "svg_path": " ".join(paths),
        "width": width,
        "height": height,
        "contour_count": len(paths),
        "skeleton_applied": skeletonize,
        "thinning_method": thinning_method,
        "error": error,
    }


# ── 转换器主类 ─────────────────────────────────────────────────────────────────

class SVGConverter:
    """图像 → SVG 路径转换器"""

    async def convert_url_to_svg(
        self,
        image_url: str,
        simplify_epsilon: float = 2.0,
        min_contour_area: int = 100,
        *,
        skeletonize: bool = False,
    ) -> dict[str, Any]:
        """下载图片并转换为 SVG 路径（OpenCV 处理）。

        Args:
            image_url: 图片 URL。
            simplify_epsilon: Douglas-Peucker 简化容差（像素）。
            min_contour_area: 非骨架模式下最小轮廓面积过滤阈值。
            skeletonize: True 先细化为单像素骨架再提取路径，适合笔绘机
                         单线绘图，避免双线轮廓；False 保留原有轮廓面模式（库默认）。
        """
        try:
            image_data = await _download_image(image_url)
            gray, binary = _preprocess_image(image_data)
            svg_paths, thinning_method = _extract_svg_paths(
                binary, simplify_epsilon, min_contour_area, skeletonize=skeletonize
            )
            h, w = gray.shape
            if not svg_paths:
                if skeletonize:
                    return _svg_payload(
                        "failed",
                        skeletonize=True,
                        error="No stroke paths after skeletonization",
                    )
                svg_paths = [_legacy_fallback_path(w, h)]
            return _svg_payload(
                "success",
                svg_paths=svg_paths,
                width=w,
                height=h,
                skeletonize=skeletonize,
                thinning_method=thinning_method,
            )
        except httpx.HTTPError as e:
            logger.error(f"下载图片失败: {e}")
            return _svg_payload("failed", error=f"Download failed: {e}")
        except Exception as e:
            logger.error(f"转换失败: {e}")
            return _svg_payload("failed", error=str(e))
