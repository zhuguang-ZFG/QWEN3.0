# Phase 5：XiaoZhi v1 Compat 拆分收尾设计

**日期：** 2026-06-13
**状态：** ✅ Slice 5-A/B/C 已完成（2026-06-13）
**前置：** 路由权威 Phase 4 已完成；2026-06-11 已提取 `routes/xiaozhi_compat/*` 但未删除主文件重复代码。

## 1. 问题陈述

| 文件 | 当前行数 | 红线 | 问题 |
|------|---------:|------|------|
| `routes/xiaozhi_v1_compat.py` | ~518 | ≤300 | 与子模块 **重复** 整段 helper；仅末尾 `include_router` 有效 |
| `routes/xiaozhi_compat/shared.py` | ~473 | ≤300 | 单文件聚合 DB/JWT/payload/gateway，超标 |

**边界原则（device gateway vs compat）：**

- **`routes/xiaozhi_v1_compat*`**：OpenAPI 兼容 REST（`/api/v1/*`），账号/设备/任务/成员 SQLite 映射。
- **`device_gateway/` + `routes/device_gateway*`**：MQTT/WS/HTTP 设备会话、任务队列、执行 dispatch。
- **桥接点：** `shared.gateway` 的 `build_gateway_task` / `dispatch_or_enqueue` — compat 意图 → gateway task → `device_gateway_dispatch`。

不在本阶段重写 device_gateway；仅收敛 compat 层文件边界。

## 2. 目标结构

```text
routes/
├── xiaozhi_v1_compat.py          # ≤80 行：APIRouter + include_router + 测试用 re-export
└── xiaozhi_compat/
    ├── constants.py              # ALLOWED_* 枚举
    ├── db.py                     # connect / ensure_schema
    ├── auth.py                   # JWT / authorize
    ├── http_helpers.py           # ok / err / read_body / 时间 & 解析
    ├── payloads.py               # *_payload 序列化
    ├── access.py                 # 设备权限 / supply 解析 / transfer 过期
    ├── gateway.py                # intent → gateway task + dispatch
    ├── activation.py             # 设备配对激活码状态机
    ├── shared.py                 # 兼容 barrel（from .db import …）供既有 import 不变
    ├── user_routes.py
    ├── device_routes.py
    ├── task_routes.py
    ├── member_routes.py
    └── misc_routes.py
```

## 3. 分步实施

### Slice 5-A（本 PR）

1. 删除 `xiaozhi_v1_compat.py` 中与子模块重复的 helper（~450 行）。
2. 主文件保留 router 注册 + 测试向后兼容 re-export：`_connect`、`_schema_ready_paths`、`jwt`。
3. `pytest tests/test_xiaozhi_v1_compat_p0.py tests/test_xiaozhi_v1_compat_p1.py -q`

### Slice 5-B（本 PR）

1. 拆分 `shared.py` → `constants` / `db` / `auth` / `http_helpers` / `payloads` / `access` / `gateway`。
2. `shared.py` 改为 thin barrel，**不修改** 各 `*_routes.py` 的 `from .shared import …`。
3. 同上 pytest + `tests/test_route_registry.py`

### Slice 5-C（本 PR）

1. 拆分 `device_routes.py` 内 activation 状态机 → `routes/xiaozhi_compat/activation.py`。
2. `device_routes.py` 从 231 行降至 185 行，`activation.py` 65 行。
3. 同上 pytest。

**延后：** OpenAPI 路径与 `docs/xiaozhi_api_openapi.yaml` 逐条对齐审计。

## 4. 非目标

- 不改 REST 路径、响应 JSON 形状、JWT 字段。
- 不合并 `device_gateway` 与 compat 为单模块。
- 不在本阶段动 `admin_api_extra.py` / `chat_endpoints.py` 超标文件。

## 5. 验收

```powershell
python -m pytest tests/test_xiaozhi_v1_compat_p0.py tests/test_xiaozhi_v1_compat_p1.py tests/test_route_registry.py -q
python scripts/repo_stats.py  # xiaozhi_v1_compat + shared 均 ≤300
```

## 6. 回滚

- VPS 备份标签沿用 `deploy_unified --files routes/xiaozhi_v1_compat.py routes/xiaozhi_compat/`
- 单 commit revert 即可恢复 monolith
