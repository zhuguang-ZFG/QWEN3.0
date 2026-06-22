"""
LiMa 特性生成规划器 — 模板模式库。

从 `lima_feature_planner.py` 提取，保持独立以便维护。
"""

# ========== 模式库 ==========

PATTERNS = {
    "route": {
        "description": "FastAPI 路由端点",
        "file_template": """
\"\"\"{description}\"\"\"

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key

router = APIRouter(prefix="/{prefix}", tags=["{tag}"])

""",
    },
    "device_route": {
        "reference": "routes/device_ota.py",
        "description": "设备端 API（带设备认证）",
        "file_template": """
\"\"\"{description}\"\"\"

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from access_guard import extract_bearer_token
from device_gateway.auth import validate_device_token

router = APIRouter(prefix="/device/v1/{resource}", tags=["device-{tag}"])


def _require_device_token(device_id: str, authorization: str) -> None:
    token = extract_bearer_token(authorization)
    if not validate_device_token(device_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")

""",
    },
    "service_class": {
        "description": "服务类（无状态/可注入）",
        "file_template": """
\"\"\"{description}\"\"\"

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class {ClassName}:
    \"\"\"{description}\"\"\"

    def __post_init__(self) -> None:
        _log.info("{ClassName} initialized")

""",
    },
    "test_pattern": {
        "description": "测试文件",
        "reference": "tests/test_device_ota.py",
        "init_file": """
import pytest
from fastapi.testclient import TestClient

""",
    },
}
