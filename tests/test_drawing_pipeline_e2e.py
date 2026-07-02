"""run_pipeline 端到端测试 — 验证完整管道组合。"""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
from PIL import Image  # noqa: E402

from xiaozhi_drawing.pipeline import (  # noqa: E402
    PipelineConfig,
    PipelineContext,
    order_stage,
    preprocess_stage,
    run_pipeline,
    simplify_stage,
    trace_stage,
)


def _horizontal_line_binary(width: int = 40, height: int = 20, thickness: int = 5) -> np.ndarray:
    binary = np.zeros((height, width), dtype=np.uint8)
    y0 = height // 2 - thickness // 2
    binary[y0 : y0 + thickness, :] = 255
    return binary


def _png_bytes(img: Image.Image) -> BytesIO:
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


class TestRunPipeline:
    def test_full_skeleton_pipeline(self):
        """完整骨架管道：preprocess -> trace -> order -> simplify。"""
        img = Image.new("RGB", (100, 100), "white")
        arr = np.array(img)
        cv2.line(arr, (10, 50), (90, 50), (0, 0, 0), 8)
        img = Image.fromarray(arr)

        ctx = PipelineContext(
            image_data=_png_bytes(img),
            config=PipelineConfig(
                skeletonize=True,
                simplify_epsilon=2.0,
                min_contour_area=1,
                min_stroke_length=5.0,
                reorder_strokes=True,
            ),
        )
        stages = [preprocess_stage, trace_stage, order_stage, simplify_stage]
        ctx = run_pipeline(ctx, stages)

        assert ctx.threshold_method in {"otsu", "adaptive"}
        assert ctx.thinning_method in {"skimage", "ximgproc", "morphological"}
        assert len(ctx.svg_paths) >= 1
        assert all(" Z" not in p for p in ctx.svg_paths)

    def test_full_legacy_pipeline(self):
        """完整 legacy 管道：preprocess -> trace -> simplify（闭合路径）。"""
        img = Image.new("RGB", (100, 100), "white")
        arr = np.array(img)
        cv2.circle(arr, (50, 50), 30, (0, 0, 0), -1)
        img = Image.fromarray(arr)

        ctx = PipelineContext(
            image_data=_png_bytes(img),
            config=PipelineConfig(
                skeletonize=False,
                simplify_epsilon=2.0,
                min_contour_area=100,
            ),
        )
        stages = [preprocess_stage, trace_stage, simplify_stage]
        ctx = run_pipeline(ctx, stages)

        assert len(ctx.svg_paths) >= 1
        assert all(" Z" in p for p in ctx.svg_paths)
        assert ctx.thinning_method is None

    def test_empty_image_skeleton_pipeline(self):
        """空白图骨架管道应产出空路径列表。"""
        img = Image.new("RGB", (40, 40), "white")
        ctx = PipelineContext(
            image_data=_png_bytes(img),
            config=PipelineConfig(skeletonize=True, min_contour_area=1),
        )
        ctx = run_pipeline(ctx, [preprocess_stage, trace_stage, simplify_stage])
        assert ctx.svg_paths == []

    def test_pipeline_is_composable(self):
        """管道可自由增减阶段。"""
        binary = _horizontal_line_binary()
        ctx = PipelineContext(
            binary=binary,
            config=PipelineConfig(skeletonize=True, simplify_epsilon=1.0, min_stroke_length=1.0),
        )
        # 只跑 trace + simplify，不跑 order
        ctx = run_pipeline(ctx, [trace_stage, simplify_stage])
        assert len(ctx.svg_paths) >= 1
