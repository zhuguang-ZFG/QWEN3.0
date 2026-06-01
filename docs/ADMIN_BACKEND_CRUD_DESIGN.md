# Admin Backend CRUD — 设计文档

> Superpowers-1 · 2026-06-02

## 目标

在 LiMa 管理面板中实现后端 CRUD（创建/读取/更新/删除/测试），遵循 Superpowers 原则。

## 架构决策

### 存储方案：JSON overlay（非源码改写）

不改写 `backends_registry.py`，而是在 `data/backend_overrides.json` 中存储增删改操作。
`backends_registry.py` 在加载时 merge overlay：

```python
# backends_registry.py 末尾
_overlay = _load_overlay("data/backend_overrides.json")
for name, cfg in _overlay.get("add", {}).items():
    BACKENDS[name] = cfg
for name in _overlay.get("delete", []):
    BACKENDS.pop(name, None)
for name, cfg in _overlay.get("update", {}).items():
    if name in BACKENDS:
        BACKENDS[name].update(cfg)
```

### API 设计

| 方法 | 路径 | 功能 | 鉴权 |
|------|------|------|------|
| GET | `/admin/backends` | 列出所有后端 | verify_admin |
| POST | `/admin/backends` | 添加后端 | verify_admin + verify_csrf |
| PUT | `/admin/backends/{name}` | 更新后端 | verify_admin + verify_csrf |
| DELETE | `/admin/backends/{name}` | 删除后端 | verify_admin + verify_csrf |
| POST | `/admin/backends/{name}/test` | 测试后端连通性 | verify_admin |

### overlay JSON 格式

```json
{
  "add": {
    "new_backend": {"url": "...", "key": "...", "model": "...", "fmt": "openai", "timeout": 30}
  },
  "update": {
    "existing_backend": {"timeout": 60, "key": "new-key"}
  },
  "delete": ["old_backend_1", "old_backend_2"]
}
```

## 实现步骤 (Superpowers)

1. **设计文档** ✅ 本文件
2. **新增 `routes/admin_backends_crud.py`** — CRUD 端点 + overlay 读写
3. **修改 `backends_registry.py`** — 加载时 merge overlay
4. **更新 `admin.html`** — 添加 CRUD UI
5. **本地测试** — pytest
6. **部署 VPS** — deploy + smoke
