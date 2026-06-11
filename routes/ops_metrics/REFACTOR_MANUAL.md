# Ops Metrics 重构执行手册

**日期:** 2026-06-11
**执行者:** 开发者手动执行
**预计时间:** 4-5 小时
**状态:** 已创建 formatters.py，其余待执行

---

## 已完成

- ✅ 创建 `routes/ops_metrics/` 目录结构
- ✅ 创建 `formatters.py` (51 行) - 包含 redacted, backend_call_count, backend_call_detail, top_backend_counts, top_backend_details

---

## 剩余步骤

### Step 1: 完成 collectors.py (~280 行)

**迁移函数:**
从 `routes/ops_metrics.py` 移动以下函数到 `routes/ops_metrics/collectors.py`:

```python
# 需要移动的函数（按行号）:
- _app_stats() (L34-37)
- _recent_agent_tasks() (L74-100)
- _get_capability_evidence() (L103-110)
- _device_metrics() (约 L150-200)
- _session_memory_stats() (约 L200-250)
- _budget_summary() (约 L250-300)
- 其他所有 _*_stats() 和 _*_metrics() 函数
```

**导入依赖:**
```python
from typing import Any
from fastapi import Request
from .formatters import redacted
```

### Step 2: 完成 correlator.py (~150 行)

**迁移函数:**
- _sanitize_correlation()
- _correlate_by_id()
- _correlation_summary()

**导入:**
```python
from .formatters import redacted
```

### Step 3: 重构 ops_metrics.py (主文件 ~100 行)

**保留:**
- FastAPI router 定义
- 3 个端点函数 (@router.get)
- require_private_api_key 依赖

**替换导入:**
```python
from .ops_metrics.collectors import (
    app_stats, recent_agent_tasks, device_metrics,
    session_memory_stats, budget_summary, ...
)
from .ops_metrics.formatters import (
    redacted, top_backend_counts, top_backend_details
)
from .ops_metrics.correlator import (
    sanitize_correlation, correlate_by_id, correlation_summary
)
```

**重命名函数调用:**
- `_redacted()` → `redacted()`
- `_app_stats()` → `app_stats()`
- 等等

### Step 4: 更新 __init__.py

```python
"""Ops metrics submodule exports."""
from .collectors import *
from .formatters import *
from .correlator import *

__all__ = [
    "redacted", "backend_call_count", "backend_call_detail",
    "top_backend_counts", "top_backend_details",
    "app_stats", "recent_agent_tasks", "device_metrics",
    # ... 其他导出
]
```

### Step 5: 验证与测试

```bash
# 编译检查
python -m py_compile routes/ops_metrics/*.py

# 运行测试
pytest tests/test_ops_metrics.py -v

# 本地验证
curl -H "Authorization: Bearer $LIMA_API_KEY" \
  http://localhost:8080/v1/ops/metrics | jq .
```

### Step 6: 部署

```bash
python scripts/deploy_unified.py --target routes/ops_metrics
systemctl restart lima-router
curl -sf https://chat.donglicao.com/v1/ops/metrics | jq .code
```

---

## 回滚方案

```bash
git revert HEAD~1
# 或使用 VPS 备份
cd /opt/lima-router
tar xzf backups/ops-metrics-YYYYMMDD/runtime-before.tgz
systemctl restart lima-router
```

---

**当前状态:** formatters.py 已创建，其余步骤需手动执行
**预计完成剩余工作:** 3-4 小时
