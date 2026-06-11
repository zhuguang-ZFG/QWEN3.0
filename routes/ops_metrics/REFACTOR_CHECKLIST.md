# ops_metrics 重构执行检查清单

**状态:** 进行中（1/3 完成）
**剩余时间估算:** 3-4 小时

---

## ✅ 已完成

- [x] 创建子模块目录结构 `routes/ops_metrics/`
- [x] 完成 `formatters.py` (51 行，5 个函数)
  - redacted()
  - backend_call_count()
  - backend_call_detail()
  - top_backend_counts()
  - top_backend_details()
- [x] 创建空白模板文件
- [x] 创建 `REFACTOR_MANUAL.md`
- [x] 创建重构分析脚本 `scripts/refactor_ops_metrics_helper.py`

---

## 📋 待执行任务

### Task 1: 完成 collectors.py（估算 1.5h）

**需迁移的 9 个函数:**
1. `_app_stats()` (4 行) - 应用统计
2. `_recent_agent_tasks()` (27 行) - Agent 任务
3. `_get_capability_evidence()` (6 行) - 能力证据
4. `_get_cli_telemetry()` (6 行) - CLI 遥测
5. `_get_backend_telemetry()` (6 行) - 后端遥测
6. `_get_routing_guard()` (6 行) - 路由守卫
7. `_backend_recovery_snapshot()` (11 行) - 后端恢复
8. `_ops_metrics_snapshot()` (147 行) ⚠️ **最复杂**
9. `_ops_summary_from_metrics()` (69 行)

**执行步骤:**
```python
# 1. 复制函数到 collectors.py
# 2. 添加导入
from typing import Any
from fastapi import Request
from .formatters import redacted

# 3. 重命名（移除下划线前缀）
_app_stats → app_stats
_recent_agent_tasks → recent_agent_tasks
# ... 等等

# 4. 测试编译
python -m py_compile routes/ops_metrics/collectors.py
```

### Task 2: 提取 correlator.py（估算 1h）

**需提取的逻辑:**
- 从 `ops_correlate()` 端点中提取关联逻辑
- 从 `ops_correlate_summary()` 端点中提取摘要逻辑
- 创建独立函数: `correlate_by_id()`, `correlation_summary()`

**预计行数:** ~150 行

### Task 3: 重构主文件（估算 1h）

**保留内容:**
- FastAPI router 定义
- 3 个端点函数
- 依赖注入

**修改内容:**
```python
# 替换导入
from .ops_metrics.collectors import (
    app_stats, recent_agent_tasks, ops_metrics_snapshot, ...
)
from .ops_metrics.formatters import (
    redacted, top_backend_counts, ...
)
from .ops_metrics.correlator import (
    correlate_by_id, correlation_summary
)

# 更新函数调用（移除下划线）
stats = _app_stats(request) → stats = app_stats(request)
```

### Task 4: 更新 __init__.py（估算 15min）

```python
"""Ops metrics submodule."""
from .collectors import *
from .formatters import *
from .correlator import *
```

### Task 5: 测试验证（估算 30min）

```bash
# 编译检查
python -m py_compile routes/ops_metrics/*.py

# 单元测试
pytest tests/test_ops_metrics.py -v

# 本地端到端
curl -H "Authorization: Bearer $LIMA_API_KEY" \
  http://localhost:8080/v1/ops/metrics | jq .
```

---

## ⚠️ 注意事项

1. **_ops_metrics_snapshot()** 最复杂（147行），包含大量 try/except ImportError
2. 所有 `_redacted()` 调用需改为 `redacted()`
3. 保持现有 ImportError 降级逻辑不变
4. 每完成一个模块立即测试编译

---

## 🚀 快速启动

```bash
# 1. 运行分析脚本
python scripts/refactor_ops_metrics_helper.py

# 2. 按照本清单逐项执行
# 3. 每步完成后 git commit
# 4. 全部完成后运行测试
```

---

**当前状态:** formatters.py 完成，collectors.py 待执行
**下一步:** 手动迁移 collectors.py 的 9 个函数
