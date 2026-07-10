"""OpenCV 5 + drawing pipeline smoke tests after dependency upgrades."""

from __future__ import annotations

import io

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
from PIL import Image  # noqa: E402

from xiaozhi_drawing.binarize import otsu_binary  # noqa: E402
from xiaozhi_drawing.pipeline import (  # noqa: E402
    PipelineConfig,
    PipelineContext,
    preprocess_stage,
    run_pipeline,
    simplify_stage,
    trace_stage,
)
from xiaozhi_drawing.svg_converter import SVGConverter  # noqa: E402


def test_opencv_major_version_is_five() -> None:
    major = int(cv2.__version__.split(".", 1)[0])
    assert major >= 5, f"expected OpenCV 5.x, got {cv2.__version__}"


def test_opencv5_otsu_binary_smoke() -> None:
    gray = np.zeros((24, 48), dtype=np.uint8)
    gray[10:14, :] = 255
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = otsu_binary(blurred)
    assert binary.shape == gray.shape
    assert int(binary.sum()) > 0


@pytest.mark.asyncio
async def test_svg_converter_bytes_smoke_opencv5() -> None:
    arr = np.ones((80, 80, 3), dtype=np.uint8) * 255
    cv2.rectangle(arr, (20, 20), (60, 60), (0, 0, 0), thickness=-1)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")

    converter = SVGConverter()
    result = await converter.convert_bytes_to_svg(
        buf.getvalue(),
        skeletonize=False,
        reorder_strokes=False,
        threshold_mode="otsu",
    )
    assert result.get("status") == "success"
    assert result.get("svg_path")
    assert str(result["svg_path"]).startswith("M")


def test_run_pipeline_preprocess_trace_smoke() -> None:
    arr = np.ones((64, 64, 3), dtype=np.uint8) * 255
    cv2.line(arr, (8, 32), (56, 32), (0, 0, 0), 4)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")

    ctx = PipelineContext(
        image_data=buf,
        config=PipelineConfig(skeletonize=False, min_contour_area=1, min_stroke_length=3.0),
    )
    ctx = run_pipeline(ctx, [preprocess_stage, trace_stage, simplify_stage])
    assert ctx.threshold_method in {"otsu", "adaptive", "auto"}
    assert len(ctx.svg_paths) >= 1
