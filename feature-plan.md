# 📋 特性生成规划: 添加 OTA 分段升级

## 涉及系统
- `device_ota`

## 参考模式
- **device_route**: 设备端 API（带设备认证）

## 参考文件
- `routes/device_ota.py` (212 行)
  路由: GET /release/status, POST /release/criteria, POST /deploy/{version}, GET /canary/status, POST /canary/devices/{device_id}
- `device_ota/release.py` (48 行)
- `tests/test_device_ota.py` (200 行)

## 生成顺序
  **Step 2**: CREATE `routes/添加_ota_分段升级.py`
  原因: 设备端 OTA API 端点
  **Step 3**: MODIFY `routes/route_registry.py`
  原因: 注册新路由到 route_registry.py

## 文件模板
### 模板: device_route
"""{description}"""

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

## 参考代码摘录
### routes/device_ota.py: imports
  from __future__ import annotations
  import os
  import re
  from fastapi import APIRouter, Body, Depends, Header, HTTPException
  from fastapi.responses import JSONResponse
  from access_guard import require_private_api_key
  from access_guard import extract_bearer_token
  from device_gateway.auth import validate_device_token
### routes/device_ota.py: 路由
  @router.GET(/release/status)
  @router.POST(/release/criteria)
  @router.POST(/deploy/{version})
  @router.GET(/canary/status)
  @router.POST(/canary/devices/{device_id})

### device_ota/release.py: imports
  from __future__ import annotations
  from pathlib import Path
  from device_ota.state_store import load_state, save_section

### tests/test_device_ota.py: imports
  from device_ota.release import ReleaseGate
  from device_ota.canary import CanaryDeployment
