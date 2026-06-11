# Ops Metrics 拆分计划

**日期:** 2026-06-11
**目标:** 将 `routes/ops_metrics.py` (635行) 拆分为 3 个子模块，符合 Superpowers Principle 2 (≤300行/文件)
**优先级:** P1
**状态:** 计划中

---

## 一、当前状态

**文件:** `routes/ops_metrics.py`
**行数:** 635 行（违规 2x）
**端点数:** 3 个 REST 端点

### 功能分类（通过代码审查）

#### 1. 核心端点定义 (约 150 行)
- `GET /v1/ops/metrics` - 统一监控快照
- `GET /v1/ops/correlate` - 跨系统追踪
- `GET /v1/ops/correlate/summary` - 关联摘要

#### 2. 数据收集器 (约 300 行)
- `_app_stats()` - 应用层统计
- `_backend_call_count()` / `_backend_call_detail()` - 后端调用统计
- `_top_backend_counts()` / `_top_backend_details()` - 排名聚合
- `_recent_agent_tasks()` - Agent 任务快照
- `_device_metrics()` - 设备网关指标
- `_session_memory_stats()` - 会话内存统计
- `_budget_summary()` - 预算汇总
- 以及其他 10+ 收集函数

#### 3. Redaction & Formatting (约 180 行)
- `_redacted()` - 敏感信息脱敏
- `_sanitize_correlation()` - 关联数据清洗
- JSON 响应格式化
- 时间戳转换

---

## 二、拆分方案

### 目标结构

```
routes/
├── ops_metrics.py (保留，路由入口，约 100 行)
└── ops_metrics/
    ├── __init__.py (导出所有收集器)
    ├── collectors.py (数据收集器，约 280 行)
    ├── formatters.py (格式化与脱敏，约 120 行)
    └── correlator.py (关联追踪逻辑，约 150 行)
```

### 模块职责

#### `ops_metrics/collectors.py` (~280 行)
- 所有 `_*_stats()` / `_*_metrics()` 函数
- 后端统计聚合函数
- Agent/Device/Session 数据读取

#### `ops_metrics/formatters.py` (~120 行)
- `_redacted()` - 脱敏工具
- `_backend_call_count()` / `_backend_call_detail()` - 数据转换
- `_top_backend_counts()` / `_top_backend_details()` - 排名格式化
- 时间戳工具

#### `ops_metrics/correlator.py` (~150 行)
- `_sanitize_correlation()` - 关联数据处理
- 跨系统 ID 追踪逻辑
- 关联摘要生成

#### `ops_metrics.py` (主文件，~100 行)
- FastAPI 路由定义
- 依赖注入 (`require_private_api_key`)
- 从子模块组装响应

---

## 三、迁移步骤

### Phase 1: 创建子模块结构 (20 分钟)

```bash
mkdir -p routes/ops_metrics
touch routes/ops_metrics/__init__.py
touch routes/ops_metrics/collectors.py
touch routes/ops_metrics/formatters.py
touch routes/ops_metrics/correlator.py
```

### Phase 2: 迁移格式化工具 (30 分钟)

1. 将 `_redacted()`, `_backend_call_*()`, `_top_backend_*()` 移至 `formatters.py`
2. 添加类型注解
3. 本地 `python -m py_compile routes/ops_metrics/formatters.py`

### Phase 3: 迁移数据收集器 (1 小时)

1. 将所有 `_*_stats()` / `_*_metrics()` 函数移至 `collectors.py`
2. 从 `formatters` 导入格式化工具
3. 测试导入：`python -c "from routes.ops_metrics.collectors import _app_stats"`

### Phase 4: 迁移关联逻辑 (45 分钟)

1. 将 `_sanitize_correlation()` 及相关函数移至 `correlator.py`
2. 从 `formatters` 导入脱敏工具
3. 本地编译验证

### Phase 5: 重构主文件 (45 分钟)

1. 精简 `ops_metrics.py` 为路由定义
2. 从子模块导入收集器和格式化器
3. 保持端点签名不变

### Phase 6: 测试与验证 (1 小时)

```bash
# 单元测试
pytest tests/test_ops_metrics.py -v

# Lint 检查
ruff check routes/ops_metrics/

# 本地端到端
curl -H "Authorization: Bearer $LIMA_API_KEY" \
  http://localhost:8080/v1/ops/metrics | jq .
```

### Phase 7: 部署验证 (30 分钟)

```bash
# VPS 部署
python scripts/deploy_unified.py --target routes/ops_metrics

# 生产验证
curl -sf https://chat.donglicao.com/v1/ops/metrics \
  -H "Authorization: Bearer $PROD_KEY" | jq .code
```

---

## 四、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 循环依赖 | 🟡 Medium | `formatters` 只包含纯函数，不导入 `collectors` |
| ImportError 降级 | 🟢 Low | 保持现有 `try/except ImportError` 模式 |
| 性能回退 | 🟢 Low | 子模块导入在服务启动时完成，运行时无额外开销 |

---

## 五、验收标准

### 必须通过

1. ✅ 所有子模块 ≤ 300 行
2. ✅ `pytest tests/test_ops_metrics.py` - 所有测试通过
3. ✅ `ruff check routes/ops_metrics/` - 无 lint 错误
4. ✅ 公网 `/v1/ops/metrics` 返回 `{"code": 0, ...}`
5. ✅ 无循环导入

### 建议通过

- 响应时间 ≤ 原单文件的 1.1x
- 内存占用无明显增加

---

## 六、执行时间估算

**总计:** 约 4-5 小时（包含测试与部署）

**建议执行时间:** 1 个工作日

---

## 七、回滚计划

```bash
git revert HEAD~1
cd /opt/lima-router
tar xzf backups/ops-metrics-refactor-YYYYMMDD/runtime-before.tgz
systemctl restart lima-router
```

---

**状态:** 计划已完成，等待执行确认
