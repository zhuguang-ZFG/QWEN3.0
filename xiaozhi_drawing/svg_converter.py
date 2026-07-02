"""图像转 SVG 路径转换器 — 公共 API + 管道封装。

处理逻辑已拆分至 :mod:`xiaozhi_drawing.pipeline`，本模块保留公共 API
（:class:`SVGConverter`）和向后兼容的私有函数接口。
"""

from io import BytesIO
import logging
from typing import Any

import httpx
import numpy as np

try:
    import cv2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - local environments may omit OpenCV
    cv2 = None

from xiaozhi_drawing.binarize import binarize as _binarize  # noqa: F401 — re-export for tests
from xiaozhi_drawing.pipeline import (
    PipelineConfig,
    PipelineContext,
    order_stage,
    preprocess_stage,
    run_pipeline,
    simplify_stage,
    thin_binary as _thin_binary,  # noqa: F401 — re-export for tests
    thin_morphological as _thin_morphological,  # noqa: F401 — re-export for tests
    trace_stage,
)

logger = logging.getLogger(__name__)

__all__ = ["SVGConverter"]


# --------------------------------------------------------------------------- #
#  向后兼容的私有函数（委托至管道阶段）
# --------------------------------------------------------------------------- #


def _preprocess_image(image_data: BytesIO, threshold_mode: str = "auto") -> tuple:
    """加载、缩放、灰度、模糊、二值化。向后兼容包装器。"""
    ctx = PipelineContext(
        image_data=image_data,
        config=PipelineConfig(threshold_mode=threshold_mode),
    )
    ctx = preprocess_stage(ctx)
    return ctx.gray, ctx.binary, ctx.threshold_method


def _contour_to_svg_path(contour: np.ndarray, *, closed: bool = True) -> str:
    """OpenCV 轮廓数组 → SVG path 字符串。

    Args:
        contour: OpenCV contour array (N, 1, 2)。
        closed: True → 追加 Z（轮廓/填充模式）。
                False → 开放路径（单笔画笔绘模式，无 Z）。
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
    spur_length_threshold: int = 10,
    min_stroke_length: float = 5.0,
    reorder_strokes: bool = False,
) -> tuple[list[str], str | None]:
    """提取 SVG 路径。向后兼容包装器 — 委托至管道阶段。

    skeletonize=True (笔绘模式): 细化→修剪→追踪开放路径
    skeletonize=False (legacy 模式): 外轮廓→闭合路径
    """
    cfg = PipelineConfig(
        simplify_epsilon=simplify_epsilon,
        min_contour_area=min_contour_area,
        skeletonize=skeletonize,
        spur_length_threshold=spur_length_threshold,
        min_stroke_length=min_stroke_length,
        reorder_strokes=reorder_strokes,
    )
    ctx = PipelineContext(binary=binary, config=cfg)
    ctx = run_pipeline(ctx, [trace_stage, order_stage, simplify_stage])
    return ctx.svg_paths, ctx.thinning_method


# --------------------------------------------------------------------------- #
#  结果构建
# --------------------------------------------------------------------------- #


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
    threshold_method: str | None = None,
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
        "threshold_method": threshold_method,
        "error": error,
    }


# --------------------------------------------------------------------------- #
#  核心转换
# --------------------------------------------------------------------------- #


async def _download_image(image_url: str) -> BytesIO:
    """Download image from URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        return BytesIO(resp.content)


async def _convert_image_bytes(
    image_data: BytesIO,
    *,
    simplify_epsilon: float,
    min_contour_area: int,
    skeletonize: bool,
    threshold_mode: str,
    spur_length_threshold: int,
    min_stroke_length: float,
    reorder_strokes: bool,
) -> dict[str, Any]:
    """Convert already-downloaded image bytes to an SVG result dict."""
    try:
        gray, binary, threshold_method = _preprocess_image(image_data, threshold_mode)
        svg_paths, thinning_method = _extract_svg_paths(
            binary,
            simplify_epsilon,
            min_contour_area,
            skeletonize=skeletonize,
            spur_length_threshold=spur_length_threshold,
            min_stroke_length=min_stroke_length,
            reorder_strokes=reorder_strokes,
        )
        h, w = gray.shape
        if not svg_paths:
            if skeletonize:
                return _svg_payload(
                    "failed",
                    skeletonize=True,
                    threshold_method=threshold_method,
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
            threshold_method=threshold_method,
        )
    except Exception as e:
        logger.error(f"转换失败: {e}")
        return _svg_payload("failed", error=str(e))


class SVGConverter:
    """图像 → SVG 路径转换器"""

    async def convert_url_to_svg(
        self,
        image_url: str,
        simplify_epsilon: float = 2.0,
        min_contour_area: int = 100,
        *,
        skeletonize: bool = False,
        threshold_mode: str = "auto",
        spur_length_threshold: int = 10,
        min_stroke_length: float = 5.0,
        reorder_strokes: bool = False,
    ) -> dict[str, Any]:
        """Download image URL and convert to SVG paths."""
        try:
            image_data = await _download_image(image_url)
        except Exception as e:
            logger.error(f"下载图片失败: {e}")
            return _svg_payload("failed", error=f"Download failed: {e}")
        return await _convert_image_bytes(
            image_data,
            simplify_epsilon=simplify_epsilon,
            min_contour_area=min_contour_area,
            skeletonize=skeletonize,
            threshold_mode=threshold_mode,
            spur_length_threshold=spur_length_threshold,
            min_stroke_length=min_stroke_length,
            reorder_strokes=reorder_strokes,
        )

    async def convert_bytes_to_svg(
        self,
        image_bytes: bytes,
        simplify_epsilon: float = 2.0,
        min_contour_area: int = 100,
        *,
        skeletonize: bool = False,
        threshold_mode: str = "auto",
        spur_length_threshold: int = 10,
        min_stroke_length: float = 5.0,
        reorder_strokes: bool = False,
    ) -> dict[str, Any]:
        """Convert already-loaded image bytes to SVG paths."""
        return await _convert_image_bytes(
            BytesIO(image_bytes),
            simplify_epsilon=simplify_epsilon,
            min_contour_area=min_contour_area,
            skeletonize=skeletonize,
            threshold_mode=threshold_mode,
            spur_length_threshold=spur_length_threshold,
            min_stroke_length=min_stroke_length,
            reorder_strokes=reorder_strokes,
        )
