# 后端稳定性增强设计

> 日期: 2026-05-21
> 状态: 设计中
> 优先级: P0（指数退避 + 质量追踪）→ P1（健康评分 + 预算）

---

## 一、问题分析

### 现状

LiMa 路由 100+ 后端，稳定性问题集中在：

| 问题 | 频率 | 影响 |
|------|------|------|
| 后端返回错误消息伪装正常回答 | 高 | 用户看到"服务繁忙" |
| 429 限流导致 cooldown 级联 | 高 | 大面积后端不可用 |
| 免费后端额度耗尽无预警 | 中 | 突然全部失败 |
| 固定 5s cooldown 反复撞墙 | 中 | 浪费请求、延迟增加 |
| 被动健康追踪滞后 | 中 | 首个请求必然失败 |

### 已修复（本次）

- `http_caller.py`: 后端错误消息检测 + 流式缓冲
- `server.py`: `_quality_check` 扩展 + Anthropic fallback 改用 routing_engine

### 待解决（本文档范围）

1. 指数退避 cooldown
2. 响应质量追踪
3. 健康评分 + 加权路由
4. 请求预算管理

---

## 二、P0-A：指数退避 Cooldown

### 设计目标

替代固定 5s cooldown，避免对持续故障后端反复重试。

### 当前实现（health_tracker.py）

```python
COOLDOWN_TTL = 5  # 固定 5 秒
_cooldown_cache = {}  # {backend: expire_time}
```

### 新设计

```python
# 退避参数
BASE_COOLDOWN = 5        # 首次失败: 5s
MAX_COOLDOWN = 300       # 上限: 5分钟
BACKOFF_FACTOR = 2       # 倍增因子
RESET_AFTER_SUCCESS = 1  # 成功1次即重置

# 数据结构
_cooldown_state = {
    "backend_name": {
        "consecutive_failures": 0,
        "current_cooldown": 5,
        "cooldown_until": 0.0,
        "last_error_code": None,
    }
}
```

### 退避策略

```
失败次数  cooldown   累计等待
1         5s         5s
2         10s        15s
3         20s        35s
4         40s        75s
5         80s        155s
6         160s       315s
7+        300s(cap)  615s+
```

### 特殊规则

- **429 (Rate Limit)**: 直接跳到 30s 起步（限流通常需要更长恢复）
- **401/403 (Auth)**: 直接跳到 300s（key 失效不会自愈）
- **5xx (Server Error)**: 正常指数退避
- **成功恢复**: 一次成功即重置 consecutive_failures = 0

### 接口变更

```python
# health_tracker.py 新增/修改

def record_failure(backend: str, error_code: int = None):
    """记录失败，更新退避状态。"""
    state = _cooldown_state.setdefault(backend, _default_state())
    state["consecutive_failures"] += 1
    state["last_error_code"] = error_code
    state["current_cooldown"] = _calc_cooldown(
        state["consecutive_failures"], error_code)
    state["cooldown_until"] = time.time() + state["current_cooldown"]

def record_success(backend: str, latency_ms: float):
    """记录成功，重置退避。"""
    if backend in _cooldown_state:
        _cooldown_state[backend]["consecutive_failures"] = 0
        _cooldown_state[backend]["current_cooldown"] = BASE_COOLDOWN

def is_cooled_down(backend: str) -> bool:
    """是否在冷却期。"""
    state = _cooldown_state.get(backend)
    if not state:
        return False
    return time.time() < state["cooldown_until"]

def get_cooldown_remaining(backend: str) -> float:
    """剩余冷却秒数（调试用）。"""
    state = _cooldown_state.get(backend)
    if not state:
        return 0.0
    return max(0, state["cooldown_until"] - time.time())
```

### 与现有代码的兼容性

- `routing_engine.execute()` 调用 `health_tracker.is_cooled_down()` → 接口不变
- `routing_engine.execute()` 调用 `health_tracker.record_failure()` → 接口不变，内部逻辑升级
- `http_caller.call_api()` 调用 `health_tracker.record_success/failure()` → 同上
- 无需修改调用方代码

---

## 三、P0-B：响应质量追踪

### 设计目标

在 HTTP 状态码之外，追踪响应内容质量，提前发现后端降级。

### 追踪指标

```python
@dataclass
class BackendQuality:
    response_lengths: deque  # 最近 50 次响应长度
    empty_count: int         # 连续空响应次数
    error_msg_count: int     # 被 _is_backend_error 拦截的次数
    avg_latency_ms: float    # 滑动平均延迟
    last_success: float      # 上次成功时间戳
```

### 降级检测规则

```python
def detect_degradation(backend: str) -> str:
    """返回: 'healthy' | 'degraded' | 'dead'"""
    q = _quality_map[backend]

    # 规则1: 连续3次空响应 → dead
    if q.empty_count >= 3:
        return "dead"

    # 规则2: 最近10次中>50%被拦截为错误消息 → dead
    recent_error_rate = q.error_msg_count / max(len(q.response_lengths), 1)
    if recent_error_rate > 0.5:
        return "dead"

    # 规则3: 平均响应长度骤降(低于历史均值30%) → degraded
    if len(q.response_lengths) >= 10:
        recent_avg = mean(list(q.response_lengths)[-5:])
        historical_avg = mean(list(q.response_lengths))
        if recent_avg < historical_avg * 0.3:
            return "degraded"

    # 规则4: 延迟突增(>3x 历史均值) → degraded
    if q.avg_latency_ms > historical_latency * 3:
        return "degraded"

    return "healthy"
```

### 集成点

在 `http_caller.call_api()` 成功返回后记录：

```python
# http_caller.py call_api() 成功路径
answer = clean_response(answer, backend)
quality_tracker.record_response(backend, len(answer), latency_ms)
return answer
```

在 `routing_engine.select()` 中使用质量数据：

```python
# routing_engine.py select() 增强
def select(request_type, health_map, quality_map=None):
    backends = router_v3.select_backends(request_type, health_map)
    if quality_map:
        # 过滤掉质量降级的后端
        backends = [b for b in backends
                    if quality_map.get(b, "healthy") != "dead"]
        # degraded 后端排到末尾
        backends.sort(key=lambda b: 0 if quality_map.get(b) == "healthy" else 1)
    return backends[:MAX_FALLBACKS]
```

---

## 四、P1-A：健康评分 + 加权路由

### 设计目标

替代二元 healthy/dead 判断，用连续分数实现更精细的后端选择。

### 评分公式

```python
def compute_score(backend: str) -> float:
    """0-100 分，越高越健康。"""
    h = _health_data[backend]

    success_rate = h.successes / max(h.total, 1)      # 0-1
    latency_norm = min(h.avg_latency / 5000, 1.0)     # 归一化到 0-1 (5s=最差)
    recency = min((time.time() - h.last_success) / 300, 1.0)  # 5分钟内有成功=0

    score = (
        success_rate * 50 +          # 成功率权重最大
        (1 - latency_norm) * 30 +    # 延迟越低分越高
        (1 - recency) * 20           # 最近有成功加分
    )
    return round(score, 1)
```

### 加权选择算法

```python
def weighted_select(backends: list[str], scores: dict) -> list[str]:
    """按分数加权排序，但保留随机性避免羊群效应。"""
    scored = [(b, scores.get(b, 50)) for b in backends]
    # 分数 + 小随机扰动
    scored.sort(key=lambda x: -(x[1] + random.uniform(0, 10)))
    return [b for b, _ in scored]
```

### 与 P2C (Power of Two Choices) 的关系

`router_v3.py` 已实现 P2C 算法。健康评分可以作为 P2C 的比较依据：

```python
# router_v3.py P2C 增强
def p2c_select(pool, scores):
    a, b = random.sample(pool, 2)
    return a if scores.get(a, 50) >= scores.get(b, 50) else b
```

---

## 五、P1-B：请求预算管理

### 设计目标

给每个后端设置日请求限额，预防额度耗尽后的突然失败。

### 预算配置

```python
# backends.py 扩展
BACKEND_BUDGETS = {
    # 免费后端: 保守限额
    "longcat_chat": {"daily_limit": 2000, "warn_at": 0.8},
    "longcat_lite": {"daily_limit": 2000, "warn_at": 0.8},
    "nvidia_qwen_coder": {"daily_limit": 500, "warn_at": 0.7},

    # 逆向代理: 更保守
    "deepseek_free": {"daily_limit": 300, "warn_at": 0.6},

    # 付费: 按实际额度
    "deepseek_pro": {"daily_limit": 10000, "warn_at": 0.9},

    # 无限额度
    "cloudflare_*": {"daily_limit": None},
}
```

### 预算状态

```python
_budget_state = {
    "backend_name": {
        "used_today": 0,
        "reset_at": "2026-05-22T00:00:00",  # 每日重置
        "status": "normal",  # normal | warning | exhausted
    }
}
```

### 路由集成

```python
def is_budget_available(backend: str) -> bool:
    """预算是否还有余量。"""
    budget = BACKEND_BUDGETS.get(backend)
    if not budget or budget["daily_limit"] is None:
        return True
    state = _budget_state.get(backend, {})
    return state.get("used_today", 0) < budget["daily_limit"]

def get_budget_priority(backend: str) -> float:
    """返回 0-1 的预算优先级，越接近耗尽越低。"""
    budget = BACKEND_BUDGETS.get(backend)
    if not budget or budget["daily_limit"] is None:
        return 1.0
    used_ratio = _budget_state.get(backend, {}).get("used_today", 0) / budget["daily_limit"]
    return max(0, 1.0 - used_ratio)
```

---

## 六、实施计划

### Phase 1: P0（1-2小时）

| 步骤 | 文件 | 改动 |
|------|------|------|
| 1 | `health_tracker.py` | 重写 cooldown 逻辑为指数退避 |
| 2 | `health_tracker.py` | 新增 `BackendQuality` 数据结构 |
| 3 | `http_caller.py` | 成功时调用 `quality_tracker.record_response()` |
| 4 | 测试 | 验证退避时间正确、质量降级检测准确 |

### Phase 2: P1（半天）

| 步骤 | 文件 | 改动 |
|------|------|------|
| 5 | `health_tracker.py` | 新增 `compute_score()` |
| 6 | `routing_engine.py` | `select()` 使用质量分数排序 |
| 7 | `backends.py` | 新增 `BACKEND_BUDGETS` 配置 |
| 8 | `health_tracker.py` | 新增预算管理逻辑 |
| 9 | 测试 | 端到端验证路由选择正确性 |

### Phase 3: 部署

| 步骤 | 操作 |
|------|------|
| 10 | 本地 curl 测试全路径 |
| 11 | 上传到服务器（备份旧文件） |
| 12 | 观察 1 小时日志确认无回归 |

---

## 七、参考

- Netflix Hystrix: 熔断器 + 指数退避
- Envoy Proxy: 健康检查 + 权重路由
- gRPC: 客户端负载均衡 + P2C
- 本项目 `docs/ROUTING_ENGINE_DESIGN.md`: 五层路由架构

