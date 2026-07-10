"""Verify server_dlc registers the mini-program device_app_* routes.

阶段 A：server_dlc 补注册 device_app_* 后，微信小程序 v3.9.0 依赖的
/device/v1/app/* 端点必须可达，且 /dlc/* 与 /health 不受影响。
"""

from __future__ import annotations

from dlc_api.device_app_router import register_device_app_routes
from tests.route_paths_helpers import openapi_paths


def test_aggregator_registers_device_app_paths() -> None:
    """include_device_app_routers 把 device_app_* 路由挂到 app 上。"""
    from fastapi import FastAPI

    app = FastAPI()
    register_device_app_routes(app)
    paths = openapi_paths(app)
    app_paths = {p for p in paths if p.startswith("/device/v1/app")}
    assert len(app_paths) >= 20, f"expected many device_app paths, got {len(app_paths)}"


def test_server_dlc_exposes_device_app_and_dlc() -> None:
    """server_dlc.app 同时暴露 device_app_* 与 /dlc/* 与 /health。"""
    import server_dlc

    paths = openapi_paths(server_dlc.app)
    # 小程序核心端点
    assert "/device/v1/app/devices" in paths
    assert "/device/v1/app/devices/{device_id}/share" in paths
    assert "/device/v1/app/device/v1/app/devices/{device_id}/share" not in paths
    # 小程序 AI 绘图端点（P4/P5 误删后恢复）
    assert "/device/v1/app/images/generations" in paths
    # DLC 绘图端点保持不变
    assert "/dlc/tasks/dispatch" in paths
    assert "/dlc/tasks/preview" in paths
    assert "/health" in paths


def test_server_dlc_device_app_route_count() -> None:
    """回归护栏：device_app 路由数量不应意外骤降。"""
    import server_dlc

    paths = openapi_paths(server_dlc.app)
    app_paths = [p for p in paths if p.startswith("/device/v1/app")]
    assert len(app_paths) >= 60, f"device_app routes dropped to {len(app_paths)}"
