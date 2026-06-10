# LiMa 可观测性事件

> 创建日期: 2026-05-24
> 范围: 本地、零依赖的可观测性事件和指标模型。

## 目标

- 解释后端路由、故障、延迟、质量和令牌遥测数据。
- 保持默认可观测性为本地且内存化。
- 避免原始提示词、密钥、Cookie、文件主体和密钥持久化。
- 在接入热请求路径之前提供稳定的辅助函数。

## 事件结构

`observability.events.LiMaEvent` 包含：

- `event_type` — 事件类型
- `timestamp` — 时间戳
- `request_id` — 请求 ID
- `session_id_hash` — 会话 ID 哈希
- `backend` — 后端
- `route_reason` — 路由原因
- `latency_ms` — 延迟（毫秒）
- `failure_class` — 故障类别
- `quality_score` — 质量评分
- `cost_class` — 成本类别
- `prompt_tokens` — 提示令牌数
- `completion_tokens` — 补全令牌数
- `metadata` — 元数据

`session_id_hash` 是短 SHA-256 哈希值。原始会话 ID 不会存储。

## 事件工厂

- `request_start_event()` — 请求开始事件
- `request_end_event()` — 请求结束事件
- `backend_call_event()` — 后端调用事件
- `backend_error_event()` — 后端错误事件
- `route_decision_event()` — 路由决策事件
- `quality_result_event()` — 质量结果事件
- `key_pool_event()` — 密钥池事件
- `token_usage_event()` — 令牌使用事件

## 脱敏规则

事件构建递归地对元数据进行消毒处理。

敏感元数据键被替换为 `[REDACTED]`，包括 prompt、message、key、token、cookie、password、secret、authorization、body 和 file-body 形状的字段。

字符串值通过共享内存脱敏器处理（当可用时）。这确保事件对象即使在调用者意外地将类令牌值传递到 `metadata` 或 `key_pool_event(details=...)` 中时也是安全的。

## 指标快照

`observability.metrics.get_metrics_snapshot()` 返回：

- 总请求计数；
- 活跃哈希会话计数；
- 每个后端的成功/失败计数；
- 每个后端的平均、p50 和 p95 延迟；
- 每个后端的平均质量评分；
- 每个后端的提示/补全令牌总数；
- 故障类别计数；
- 事件类型计数。

便捷查询：

- `get_top_failing_backends(n)` — 获取失败最多的 n 个后端
- `get_top_quality_backends(n)` — 获取质量最高的 n 个后端
- `get_fastest_growing_failure_class(n)` — 获取增长最快的故障类别

## 当前边界

M6 定义了事件模型、本地指标接收器、报告、测试以及以下模块的热路径接入：

- `http_caller.py`
- `routing_engine.py`
- `routes/quality_gate.py`
- `key_pool.py`
- `budget_manager.py`

默认不启用任何导出器、网络调用、Prometheus 依赖或第三方遥测接收器。