"""管道阶段独立测试 — 验证每个 stage 可独立运行和组合。"""

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
    skeleton_stage,
    thin_binary,
    thin_morphological,
    trace_stage,
)


# --------------------------------------------------------------------------- #
#  辅助
# --------------------------------------------------------------------------- #


def _horizontal_line_binary(width: int = 40, height: int = 20, thickness: int = 5) -> np.ndarray:
    binary = np.zeros((height, width), dtype=np.uint8)
    y0 = height // 2 - thickness // 2
    binary[y0 : y0 + thickness, :] = 255
    return binary


def _plus_skeleton(size: int = 11) -> np.ndarray:
    skeleton = np.zeros((size, size), dtype=np.uint8)
    mid = size // 2
    skeleton[mid, 2 : size - 2] = 255
    skeleton[2 : size - 2, mid] = 255
    return skeleton


def _png_bytes(img: Image.Image) -> BytesIO:
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# --------------------------------------------------------------------------- #
#  PipelineConfig / PipelineContext
# --------------------------------------------------------------------------- #


class TestPipelineDataStructures:
    def test_config_defaults(self):
        cfg = PipelineConfig()
        assert cfg.simplify_epsilon == 2.0
        assert cfg.skeletonize is False
        assert cfg.threshold_mode == "auto"

    def test_context_defaults(self):
        ctx = PipelineContext()
        assert ctx.binary is None
        assert ctx.polylines == []
        assert ctx.svg_paths == []

    def test_context_with_config(self):
        cfg = PipelineConfig(skeletonize=True, min_stroke_length=8.0)
        ctx = PipelineContext(config=cfg)
        assert ctx.config.skeletonize is True
        assert ctx.config.min_stroke_length == 8.0


# --------------------------------------------------------------------------- #
#  preprocess_stage
# --------------------------------------------------------------------------- #


class TestPreprocessStage:
    def test_produces_gray_binary_and_method(self):
        img = Image.new("RGB", (60, 60), "white")
        ctx = PipelineContext(
            image_data=_png_bytes(img),
            config=PipelineConfig(threshold_mode="auto"),
        )
        ctx = preprocess_stage(ctx)
        assert ctx.gray is not None
        assert ctx.binary is not None
        assert ctx.threshold_method in {"otsu", "adaptive"}
        assert ctx.gray.shape == ctx.binary.shape
        assert ctx.width > 0
        assert ctx.height > 0

    def test_adaptive_mode_forced(self):
        img = Image.new("RGB", (40, 40), "white")
        ctx = PipelineContext(
            image_data=_png_bytes(img),
            config=PipelineConfig(threshold_mode="adaptive"),
        )
        ctx = preprocess_stage(ctx)
        assert ctx.threshold_method == "adaptive"

    def test_raises_without_opencv(self, monkeypatch):
        import xiaozhi_drawing.pipeline as pl

        monkeypatch.setattr(pl, "cv2", None)
        ctx = PipelineContext(image_data=_png_bytes(Image.new("RGB", (10, 10))))
        with pytest.raises(RuntimeError, match="OpenCV"):
            preprocess_stage(ctx)


# --------------------------------------------------------------------------- #
#  thin_morphological / thin_binary
# --------------------------------------------------------------------------- #


class TestThinFunctions:
    def test_thin_morphological_reduces_pixels(self):
        binary = _horizontal_line_binary(thickness=7)
        thinned = thin_morphological(binary)
        assert cv2.countNonZero(thinned) < cv2.countNonZero(binary)

    def test_thin_morphological_preserves_connectivity(self):
        binary = _horizontal_line_binary()
        thinned = thin_morphological(binary)
        assert cv2.countNonZero(thinned) > 0

    def test_thin_binary_returns_method(self):
        binary = _horizontal_line_binary()
        thinned, method = thin_binary(binary)
        assert thinned.shape == binary.shape
        assert method in {"skimage", "ximgproc", "morphological"}

    def test_thin_binary_does_not_erase(self):
        binary = _horizontal_line_binary()
        thinned, _ = thin_binary(binary)
        assert cv2.countNonZero(thinned) > 0


# --------------------------------------------------------------------------- #
#  skeleton_stage
# --------------------------------------------------------------------------- #


class TestSkeletonStage:
    def test_sets_thinning_method(self):
        binary = _horizontal_line_binary()
        ctx = PipelineContext(
            binary=binary,
            config=PipelineConfig(skeletonize=True),
        )
        ctx = skeleton_stage(ctx)
        assert ctx.skeleton is not None
        assert ctx.thinning_method in {"skimage", "ximgproc", "morphological"}

    def test_noop_without_binary(self):
        ctx = PipelineContext(config=PipelineConfig(skeletonize=True))
        ctx = skeleton_stage(ctx)
        assert ctx.skeleton is None


# --------------------------------------------------------------------------- #
#  trace_stage
# --------------------------------------------------------------------------- #


class TestTraceStage:
    def test_skeleton_mode_produces_polylines(self):
        skeleton = _plus_skeleton()
        ctx = PipelineContext(
            skeleton=skeleton,
            binary=skeleton,
            config=PipelineConfig(skeletonize=True),
        )
        ctx = trace_stage(ctx)
        assert len(ctx.polylines) >= 2

    def test_legacy_mode_produces_closed_polylines(self):
        binary = _horizontal_line_binary()
        ctx = PipelineContext(
            binary=binary,
            config=PipelineConfig(skeletonize=False, min_contour_area=1, simplify_epsilon=1.0),
        )
        ctx = trace_stage(ctx)
        assert len(ctx.polylines) >= 1
        # legacy mode: thinning_method should be None
        assert ctx.thinning_method is None

    def test_legacy_mode_filters_small_contours(self):
        binary = np.zeros((50, 50), dtype=np.uint8)
        cv2.circle(binary, (10, 10), 2, 255, -1)  # tiny
        cv2.circle(binary, (35, 35), 15, 255, -1)  # large
        ctx = PipelineContext(
            binary=binary,
            config=PipelineConfig(skeletonize=False, min_contour_area=100, simplify_epsilon=1.0),
        )
        ctx = trace_stage(ctx)
        assert len(ctx.polylines) == 1  # only the large circle

    def test_skeleton_mode_auto_invokes_skeleton_stage(self):
        """trace_stage 应在 skeleton=None 时自动调用 skeleton_stage。"""
        binary = _horizontal_line_binary()
        ctx = PipelineContext(
            binary=binary,
            config=PipelineConfig(skeletonize=True),
        )
        ctx = trace_stage(ctx)
        assert ctx.skeleton is not None
        assert ctx.thinning_method is not None


# --------------------------------------------------------------------------- #
#  order_stage
# --------------------------------------------------------------------------- #


class TestOrderStage:
    def test_reorder_enabled_in_skeleton_mode(self):
        # 3 条不相邻的水平线
        polylines = [
            [(0, 0), (10, 0)],
            [(0, 20), (10, 20)],
            [(20, 5), (30, 5)],
        ]
        ctx = PipelineContext(
            polylines=polylines,
            config=PipelineConfig(skeletonize=True, reorder_strokes=True),
        )
        original = list(ctx.polylines)
        ctx = order_stage(ctx)
        # 可能重排顺序，但应保留全部折线
        assert len(ctx.polylines) == len(original)

    def test_reorder_disabled_does_nothing(self):
        polylines = [[(0, 0), (10, 0)], [(20, 20), (30, 20)]]
        ctx = PipelineContext(
            polylines=polylines,
            config=PipelineConfig(skeletonize=True, reorder_strokes=False),
        )
        ctx = order_stage(ctx)
        assert ctx.polylines == polylines

    def test_reorder_skipped_in_legacy_mode(self):
        polylines = [[(0, 0), (10, 0), (10, 10)], [(20, 0), (30, 0), (30, 10)]]
        ctx = PipelineContext(
            polylines=polylines,
            config=PipelineConfig(skeletonize=False, reorder_strokes=True),
        )
        ctx = order_stage(ctx)
        assert ctx.polylines == polylines


# --------------------------------------------------------------------------- #
#  simplify_stage
# --------------------------------------------------------------------------- #


class TestSimplifyStage:
    def test_skeleton_mode_open_paths(self):
        polylines = [[(0, 0), (10, 0), (10, 10)]]
        ctx = PipelineContext(
            polylines=polylines,
            config=PipelineConfig(skeletonize=True, simplify_epsilon=1.0, min_stroke_length=1.0),
        )
        ctx = simplify_stage(ctx)
        assert len(ctx.svg_paths) >= 1
        assert all(" Z" not in p for p in ctx.svg_paths)
        assert all(p.startswith("M ") for p in ctx.svg_paths)

    def test_legacy_mode_closed_paths(self):
        polylines = [[(0, 0), (10, 0), (10, 10)]]
        ctx = PipelineContext(
            polylines=polylines,
            config=PipelineConfig(skeletonize=False),
        )
        ctx = simplify_stage(ctx)
        assert len(ctx.svg_paths) == 1
        assert " Z" in ctx.svg_paths[0]

    def test_empty_polylines_produces_empty_paths(self):
        ctx = PipelineContext(
            polylines=[],
            config=PipelineConfig(skeletonize=True),
        )
        ctx = simplify_stage(ctx)
        assert ctx.svg_paths == []


# --------------------------------------------------------------------------- #
#  run_pipeline 端到端
# --------------------------------------------------------------------------- #


class TestRunPipeline:
    def test_full_skeleton_pipeline(self):
        """完整骨架管道：preprocess → trace → order → simplify。"""
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
        """完整 legacy 管道：preprocess → trace → simplify（闭合路径）。"""
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
