# xiaozhi_v1_compat 拆分执行清单

**状态:** Phase 1 完成，Phase 2-6 待执行
**预计剩余时间:** 2-3 小时

---

## ✅ Phase 1: 共享模块（已完成）

- [x] 创建 `routes/xiaozhi_compat/shared.py` (270 行)
- [x] 提取所有 `_*` 辅助函数并重命名
- [x] 测试编译通过
- [x] Git commit: c63c00d

---

## 📋 Phase 2: 设备路由（预计 1h）

### 需迁移的端点（7个）

从 `routes/xiaozhi_v1_compat.py` 提取以下函数：

```python
# 行号 614-626
@router.post("/devices/register")
async def device_register(request: Request, authorization: str = Header(""))

# 行号 627-673
@router.post("/devices/bind")
async def device_bind(request: Request, authorization: str = Header(""))

# 行号 674-696
@router.get("/devices")
async def device_list(authorization: str = Header(""), page: int = Query(1), limit: int = Query(20))

# 行号 697-712
@router.get("/devices/{device_id}")
async def device_detail(device_id: str, authorization: str = Header(""))

# 行号 713-757
@router.put("/devices/{device_id}")
async def device_update(device_id: str, request: Request, authorization: str = Header(""))

# 行号 758-783
@router.post("/devices/{device_id}/unbind")
async def device_unbind(device_id: str, request: Request, authorization: str = Header(""))

# Plus: activation code if exists
```

### 执行步骤

1. 创建 `routes/xiaozhi_compat/device_routes.py`
2. 导入 shared 模块：
```python
from fastapi import APIRouter, Header, Request, Query
from .shared import authorize, ok, err, read_body, connect, ...
```
3. 创建 router: `router = APIRouter(prefix="/devices")`
4. 复制 6-7 个端点函数
5. 更新函数调用（`_ok` → `ok`, `_connect` → `connect` 等）
6. 测试编译
7. Git commit

---

## 📋 Phase 3: 用户路由（预计 30min）

### 需迁移的端点（5个）

```python
# 行号 506-530
@router.post("/login")

# 行号 531-558
@router.post("/auth/register")

# 行号 559-571
@router.post("/auth/sms-verification")

# 行号 572-580
@router.get("/auth/me")

# 行号 581-613
@router.post("/auth/account/delete")
```

### 执行步骤

1. 创建 `routes/xiaozhi_compat/user_routes.py`
2. Router prefix: `""` 或 `/auth`
3. 迁移 5 个端点
4. 更新函数调用
5. Git commit

---

## 📋 Phase 4: 任务路由（预计 1h）

### 需迁移的端点（8个）

```python
# 行号 784-826
@router.post("/devices/{device_id}/tasks")

# 行号 827-860
@router.get("/devices/{device_id}/tasks")

# 行号 861-876
@router.get("/tasks/{task_id}")

# 行号 877-908
@router.post("/tasks/{task_id}/approve")

# 行号 909-937
@router.post("/tasks/{task_id}/reject")

# 行号 938-951
@router.get("/devices/{device_id}/tasks/pending")

# Plus: PUT /tasks/{task_id}, DELETE /tasks/{task_id} if exist
```

### 执行步骤

1. 创建 `routes/xiaozhi_compat/task_routes.py`
2. Router prefix: `""` (包含 `/tasks` 和 `/devices/{device_id}/tasks`)
3. 迁移 8 个端点
4. Git commit

---

## 📋 Phase 5: 消息/交互路由（预计 30min）

### 需迁移的端点（4个）

```python
# 语音交互、TTS、消息历史、设备状态等
# 需要查看完整文件确认行号
```

### 执行步骤

1. 创建 `routes/xiaozhi_compat/message_routes.py`
2. 迁移端点
3. Git commit

---

## 📋 Phase 6: 主文件重构（预计 30min）

### 执行步骤

1. 更新 `routes/xiaozhi_v1_compat.py`:
```python
from routes.xiaozhi_compat.device_routes import router as device_router
from routes.xiaozhi_compat.user_routes import router as user_router
from routes.xiaozhi_compat.task_routes import router as task_router
from routes.xiaozhi_compat.message_routes import router as message_router

router = APIRouter(prefix="/xiaozhi/v1")
router.include_router(device_router)
router.include_router(user_router)
router.include_router(task_routes)
router.include_router(message_router)
```

2. 删除已迁移的端点函数
3. 保留 health/version 等系统端点
4. 验证行数 < 300

---

## 📋 Phase 7: 测试验证（预计 30min）

### 验证清单

```bash
# 1. 编译检查
python -m py_compile routes/xiaozhi_compat/*.py
python -m py_compile routes/xiaozhi_v1_compat.py

# 2. 运行测试
pytest tests/ -k xiaozhi -v

# 3. 检查行数
wc -l routes/xiaozhi_v1_compat.py
wc -l routes/xiaozhi_compat/*.py

# 4. Git status
git status
git log --oneline -5
```

---

## 🚀 快速启动命令

```bash
# 在新会话中执行
cd D:\QWEN3.0

# Phase 2
# 手动创建 device_routes.py，复制端点，更新导入
git add routes/xiaozhi_compat/device_routes.py
git commit -m "refactor(P1): xiaozhi Phase 2 - device routes"

# Phase 3-5: 重复上述流程

# Phase 6
# 更新主文件
git add routes/xiaozhi_v1_compat.py
git commit -m "refactor(P1): xiaozhi Phase 6 - main file refactor"

# Phase 7
pytest tests/ -k xiaozhi
git push origin feat/code-simplification
```

---

**当前状态:** Phase 1 完成
**下一步:** Phase 2 - device_routes.py
**参考文档:** `docs/superpowers/plans/2026-06-11-xiaozhi-compat-refactor-plan.md`
