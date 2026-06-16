"""Device drawing/writing model role eval specs for admission reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleEvalSpec:
    role_id: str
    label_zh: str
    backend_id: str
    implementation: str
    admission_status: str  # admitted | conditional | defer
    pytest_targets: tuple[str, ...]
    live_pytest_targets: tuple[str, ...] = ()
    pass_rate_threshold: float = 0.8
    notes: str = ""


ROLE_SPECS: tuple[RoleEvalSpec, ...] = (
    RoleEvalSpec(
        role_id="intent_parser",
        label_zh="意图解析器",
        backend_id="deterministic_intent",
        implementation="device_gateway/intent.py",
        admission_status="admitted",
        pytest_targets=(
            "tests/test_device_gateway_protocol.py",
            "tests/test_run_path_intent.py",
        ),
    ),
    RoleEvalSpec(
        role_id="text_planner",
        label_zh="文本规划器",
        backend_id="deterministic_text_render",
        implementation="device_gateway/path_pipeline.py",
        admission_status="admitted",
        pytest_targets=("tests/test_device_gateway_path_pipeline.py",),
    ),
    RoleEvalSpec(
        role_id="prompt_enhancer",
        label_zh="提示增强器",
        backend_id="pending",
        implementation="(未实现)",
        admission_status="defer",
        pytest_targets=(),
        notes="当前直接使用用户 prompt，无 LLM 增强路径",
    ),
    RoleEvalSpec(
        role_id="image_generator",
        label_zh="图像生成器",
        backend_id="dashscope_wanx",
        implementation="dashscope_image_client.py",
        admission_status="conditional",
        pytest_targets=(
            "tests/test_dashscope_image_client.py",
            "tests/test_device_gateway_model_routing.py::test_generated_drawing_uses_device_draw_route",
        ),
        live_pytest_targets=("tests/test_dashscope_image_live.py",),
        pass_rate_threshold=0.8,
        notes="条件准入：离线 mock 7 项；真实 Wanx 需 ALIYUN_API_KEY + LIMA_DEVICE_ADMISSION_LIVE=1 + --live",
    ),
    RoleEvalSpec(
        role_id="vectorizer",
        label_zh="矢量化器",
        backend_id="opencv_contour_detect",
        implementation="xiaozhi_drawing/svg_converter.py",
        admission_status="admitted",
        pytest_targets=(
            "tests/test_svg_converter.py",
            "tests/test_path_optimizer.py",
        ),
    ),
    RoleEvalSpec(
        role_id="vision_analyzer",
        label_zh="视觉分析器",
        backend_id="pending",
        implementation="(未实现)",
        admission_status="defer",
        pytest_targets=(),
        notes="设备输出图像 QC 尚未实现",
    ),
    RoleEvalSpec(
        role_id="recovery_explainer",
        label_zh="恢复解释器",
        backend_id="deterministic_error_mapping",
        implementation="device_intelligence/recovery.py",
        admission_status="admitted",
        pytest_targets=(
            "tests/test_device_intelligence_recovery.py",
            "tests/test_device_recovery_execution.py",
        ),
    ),
    RoleEvalSpec(
        role_id="route_policy",
        label_zh="路由策略契约",
        backend_id="device_role_preferences",
        implementation="device_gateway/model_routing.py",
        admission_status="admitted",
        pytest_targets=("tests/test_device_gateway_model_routing.py",),
        notes="阶段 1 契约：route_role/backend/验证/制品证据",
    ),
)


def get_role_spec(role_id: str) -> RoleEvalSpec | None:
    for spec in ROLE_SPECS:
        if spec.role_id == role_id:
            return spec
    return None
