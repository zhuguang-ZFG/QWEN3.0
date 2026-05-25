# CQ-014 Admin Routes Slice 11

## 背景

`routes/admin.py` 略超 300 行目标，且 API 与 session UI 混在同一文件。

## 拆分

| 文件 | 职责 | 行数目标 |
|------|------|----------|
| `routes/admin_state.py` | `inject_state`、共享 stats/backend 状态 | ~25 |
| `routes/admin_backends.py` | 后端元数据、`test_backend_sync` | ~120 |
| `routes/admin_api.py` | `/admin/api/*` JSON 路由 | ~180 |
| `routes/admin.py` | router 装配、login/logout/page | ~70 |

已有模块不变：`admin_auth.py`、`admin_ui.py`、`admin_agent_audit.py`。

## 兼容

- `routes.admin.inject_state` 与 `routes.admin.router` 保持不变
- `route_registry.py` 无需改动

## 验证

```bash
pytest tests/test_admin_csrf.py tests/test_admin_ui.py tests/test_admin_agent_audit.py -q
```
