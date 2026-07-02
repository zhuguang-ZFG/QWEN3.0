"""绘图路径处理管道 — 参考 vpype 的管道架构。

将图像到 SVG 路径的转换拆分为独立阶段，每个阶段可独立测试和替换。

阶段流水线:
  preprocess -> skeleton -> trace -> order -> simplify

每个阶段接收 PipelineContext 并返回更新后的 PipelineContext。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Callable

import numpy as np
from PIL import Image

try:
    import cv2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    cv2 = None

from xiaozhi_drawing.binarize import binarize as _binarize
from xiaozhi_drawing.path_ordering import reorder_polylines_nearest_neighbor
from xiaozhi_drawing.skeleton_prune import prune_skeleton_spurs
from xiaozhi_drawing.skeleton_tracer import polylines_to_svg_paths, trace_skeleton_polylines

logger = logging.getLogger(__name__)

Polyline = list[tuple[int, int]]


@dataclass
class PipelineConfig:
    """管道配置参数。"""

    simplify_epsilon: float = 2.0
    min_contour_area: int = 100
    skeletonize: bool = False
    threshold_mode: str = "auto"
    spur_length_threshold: int = 10
    min_stroke_length: float = 5.0
    reorder_strokes: bool = True


@dataclass
class PipelineContext:
    """管道上下文 — 在各阶段间传递中间状态。"""

    image_data: BytesIO | None = None
    config: PipelineConfig = field(default_factory=PipelineConfig)
    gray: np.ndarray | None = None
    binary: np.ndarray | None = None
    skeleton: np.ndarray | None = None
    polylines: list[Polyline] = field(default_factory=list)
    width: int = 0
    height: int = 0
    svg_paths: list[str] = field(default_factory=list)
    thinning_method: str | None = None
    threshold_method: str | None = None


Stage = Callable[[PipelineContext], PipelineContext]


def run_pipeline(ctx: PipelineContext, stages: list[Stage]) -> PipelineContext:
    """按顺序执行管道阶段。"""
    for stage in stages:
        ctx = stage(ctx)
    return ctx


def preprocess_stage(ctx: PipelineContext) -> PipelineContext:
    """预处理：图像 -> 灰度 -> 二值化。"""
    if cv2 is None:
        raise RuntimeError("OpenCV (cv2) is required for preprocessing")
    if ctx.image_data is None:
        raise ValueError("image_data is required for preprocess_stage")

    img = Image.open(ctx.image_data)
    arr = np.array(img)
    ctx.gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    ctx.height, ctx.width = ctx.gray.shape

    blurred = cv2.GaussianBlur(ctx.gray, (5, 5), 0)
    ctx.binary, ctx.threshold_method = _binarize(ctx.gray, blurred, ctx.config.threshold_mode)
    return ctx


def thin_morphological(binary: np.ndarray) -> np.ndarray:
    """形态学细化（ximgproc 不可用时的 fallback）。"""
    if cv2 is None:
        raise RuntimeError("OpenCV required for thin_morphological")
    if hasattr(cv2, "ximgproc"):
        return cv2.ximgproc.thinning(binary, thinningType=cv2.ximgproc.THINNING_ZHANG_SUEN)
    # Fallback: iterative erosion to approximate thinning
    thinned = binary.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    prev_count = cv2.countNonZero(thinned)
    for _ in range(20):
        eroded = cv2.erode(thinned, kernel, iterations=1)
        dilated = cv2.dilate(eroded, kernel, iterations=1)
        thinned = cv2.bitwise_and(thinned, cv2.bitwise_not(dilated))
        thinned = cv2.bitwise_or(thinned, eroded)
        curr_count = cv2.countNonZero(thinned)
        if curr_count >= prev_count:
            break
        prev_count = curr_count
    return thinned


def thin_binary(binary: np.ndarray) -> tuple[np.ndarray, str]:
    """细化二值图像，返回 (thinned, method)。"""
    try:
        from skimage.morphology import skeletonize as sk_skeletonize
        thinned = sk_skeletonize(binary > 0).astype(np.uint8) * 255
        return thinned, "skimage"
    except ImportError:
        pass

    if cv2 is not None and hasattr(cv2, "ximgproc"):
        thinned = cv2.ximgproc.thinning(binary, thinningType=cv2.ximgproc.THINNING_ZHANG_SUEN)
        return thinned, "ximgproc"

    return thin_morphological(binary), "morphological"


def skeleton_stage(ctx: PipelineContext) -> PipelineContext:
    """骨架化阶段（仅在 skeletonize=True 时执行）。"""
    if ctx.config.skeletonize and ctx.binary is not None:
        thinned, method = thin_binary(ctx.binary)
        ctx.skeleton = thinned
        ctx.thinning_method = method
        if ctx.config.spur_length_threshold > 0:
            ctx.skeleton = prune_skeleton_spurs(ctx.skeleton, ctx.config.spur_length_threshold)
    return ctx


def trace_stage(ctx: PipelineContext) -> PipelineContext:
    """轮廓/骨架追踪 -> polylines。"""
    if ctx.config.skeletonize:
        if ctx.skeleton is None and ctx.binary is not None:
            ctx = skeleton_stage(ctx)
        if ctx.skeleton is not None:
            ctx.polylines = trace_skeleton_polylines(ctx.skeleton)
    else:
        if cv2 is None or ctx.binary is None:
            return ctx
        contours, _ = cv2.findContours(ctx.binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        min_area = ctx.config.min_contour_area
        ctx.polylines = [
            [(int(p[0][0]), int(p[0][1])) for p in c]
            for c in contours
            if cv2.contourArea(c) >= min_area
        ]
    return ctx


def order_stage(ctx: PipelineContext) -> PipelineContext:
    """笔划排序（仅在骨架模式 + reorder_strokes=True 时执行）。"""
    if ctx.config.skeletonize and ctx.config.reorder_strokes and ctx.polylines:
        ctx.polylines = reorder_polylines_nearest_neighbor(ctx.polylines)
    return ctx


def simplify_stage(ctx: PipelineContext) -> PipelineContext:
    """折线简化 -> SVG 路径字符串。"""
    if not ctx.polylines:
        return ctx

    if ctx.config.skeletonize:
        ctx.svg_paths = polylines_to_svg_paths(
            ctx.polylines,
            simplify_epsilon=ctx.config.simplify_epsilon,
            min_arc_length=ctx.config.min_stroke_length,
        )
    else:
        ctx.svg_paths = [
            _points_to_closed_svg_path(pl, ctx.config.simplify_epsilon)
            for pl in ctx.polylines
            if len(pl) >= 2
        ]
    return ctx


def _points_to_closed_svg_path(
    points: list[tuple[int, int]], epsilon: float = 2.0
) -> str:
    """将点列表转换为闭合 SVG 路径。"""
    if len(points) < 2:
        return ""
    if cv2 is not None and epsilon > 0:
        arr = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
        approx = cv2.approxPolyDP(arr, epsilon, True)
        points = [(int(p[0][0]), int(p[0][1])) for p in approx]

    parts = [f"M {points[0][0]} {points[0][1]}"]
    for x, y in points[1:]:
        parts.append(f"L {x} {y}")
    parts.append("Z")
    return " ".join(parts)
