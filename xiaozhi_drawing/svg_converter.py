"""图像转 SVG 路径转换器 - OpenCV 矢量化"""

import logging
from typing import Dict, Any
from io import BytesIO
import httpx
from PIL import Image
import numpy as np
import cv2

logger = logging.getLogger(__name__)


async def _download_image(image_url: str) -> BytesIO:
    """Download image from URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        return BytesIO(resp.content)


def _preprocess_image(image_data: BytesIO) -> tuple:
    """Load, resize, gray, blur, and Otsu-threshold the image."""
    img = Image.open(image_data).convert("RGB")
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return gray, binary


def _contour_to_svg_path(contour: np.ndarray) -> str:
    """Convert an OpenCV contour to SVG path string."""
    points = contour.reshape(-1, 2)
    if len(points) == 0:
        return ""
    parts = [f"M {points[0][0]} {points[0][1]}"]
    for x, y in points[1:]:
        parts.append(f"L {x} {y}")
    parts.append("Z")
    return " ".join(parts)


def _extract_svg_paths(binary: np.ndarray, simplify_epsilon: float, min_contour_area: int) -> list[str]:
    """Find contours, filter by area, simplify, and convert to SVG paths."""
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    svg_paths = []
    for contour in contours:
        if cv2.contourArea(contour) < min_contour_area:
            continue
        approx = cv2.approxPolyDP(contour, simplify_epsilon, True)
        if len(approx) >= 3:
            path = _contour_to_svg_path(approx)
            if path:
                svg_paths.append(path)
    return svg_paths


class SVGConverter:
    """图像 → SVG 路径转换器"""

    async def convert_url_to_svg(
        self, image_url: str, simplify_epsilon: float = 2.0, min_contour_area: int = 100
    ) -> Dict[str, Any]:
        """下载图片并转换为 SVG 路径（OpenCV 轮廓检测）。"""
        try:
            image_data = await _download_image(image_url)
            gray, binary = _preprocess_image(image_data)
            svg_paths = _extract_svg_paths(binary, simplify_epsilon, min_contour_area)

            h, w = gray.shape
            if not svg_paths:
                svg_paths = [f"M 0 0 L {w} 0 L {w} {h} L 0 {h} Z"]

            return {
                "status": "success",
                "svg_path": " ".join(svg_paths),
                "width": w,
                "height": h,
                "contour_count": len(svg_paths),
                "error": None,
            }
        except httpx.HTTPError as e:
            logger.error(f"下载图片失败: {e}")
            return {
                "status": "failed",
                "svg_path": "",
                "width": 0,
                "height": 0,
                "contour_count": 0,
                "error": f"Download failed: {e}",
            }
        except Exception as e:
            logger.error(f"转换失败: {e}")
            return {"status": "failed", "svg_path": "", "width": 0, "height": 0, "contour_count": 0, "error": str(e)}
