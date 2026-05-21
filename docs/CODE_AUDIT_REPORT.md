# LiMa 全量代码审计报告

> 日期: 2026-05-21
> 审计范围: 全项目 Python 代码（4 个并行审计 agent）
> 审计维度: 安全 / 静默失败 / Python 质量 / 架构

---

## 一、问题总览

| 级别 | 数量 | 分布 |
|------|------|------|
| CRITICAL | 7 | 安全3 + 并发3 + 凭证1 |
| HIGH | 13 | 安全5 + 静默失败3 + 质量3 + 架构2 |
| MEDIUM | 12 | 各维度分散 |
| LOW | 5 | 清理项 |

---

## 二、CRITICAL 级问题（必须修复）

### C1. 管理接口无认证 [安全]
- **位置**: server.py:1837-2052（所有 `/admin/api/*` 路由）
- **影响**: 任何能访问端口的人可删除后端、触发重训练、读取用户查询日志
- **修复**: 加 `Authorization: Bearer <ADMIN_TOKEN>` 依赖注入

### C2. 未认证的子进程执行 [安全]
- **位置**: server.py:2055-2058（`POST /admin/api/retrain`）
- **影响**: 配合 C1，构成远程代码执行链
- **修复**: C1 修复后自动缓解；额外加绝对路径 + 白名单

### C3. SSRF via X-Forwarded-For [安全]
- **位置**: server.py:248, 1028
- **影响**: 攻击者注入任意 IP 到 ip-api.com 请求路径
- **修复**: 正则验证 IP 格式 + 改用 HTTPS

### C4. key_pool.py 全局锁 [并发]
- **位置**: key_pool.py:18
- **影响**: 所有 KeyPool 实例共享一把锁，高并发下全局串行化
- **修复**: 锁移入 `KeyPool.__init__` 为实例锁

### C5. probe_loop.py 线程不安全 [并发]
- **位置**: probe_loop.py:25
- **影响**: `_last_probe` 无锁读写，`_running` 标志竞态
- **修复**: 用 `threading.Event()` 替代 `_running`，加锁保护 dict

### C6. stats_collector 持锁做同步 HTTP [并发/性能]
- **位置**: stats_collector.py:59-71
- **影响**: 每个新 IP 阻塞统计锁 500ms，所有请求记录被串行化
- **修复**: IP 地理查询移出锁外，或改为异步/后台执行

### C7. Cloudflare 凭证硬编码 [凭证] (已知)
- **位置**: server.py:21-22
- **修复**: 移除默认值，纯环境变量，立即轮换 token

---

## 三、HIGH 级问题

### 安全类

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| H1 | server.py 全局 | 无速率限制 → API 配额放大攻击 | 加 slowapi 60req/min/IP |
| H2 | server.py:977 | 图片 `n` 参数无上限 → DoS | `Field(ge=1, le=10)` |
| H3 | server.py:2233 | 管理面板 innerHTML 存储型 XSS | 改用 textContent |
| H4 | server.py:1961 | 未认证注册后端 URL → SSRF | C1 修复 + URL 白名单 |
| H5 | server.py:1955 | 测试后端泄露原始响应 | 只返回状态码+延迟 |

### 静默失败类

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| H6 | server.py:1591 | `_real_stream_chunks._run()` 吞异常 | 改为 `q.put(('error', e))` |
| H7 | server.py:17-29 | `_last_resort_call` 无日志 | 加 WARNING 日志 |
| H8 | routing_engine.py:149 | force-try 吞异常不记录健康 | 加日志 + record_failure |

### 质量类

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| H9 | routing_engine.py:79 | `import random` 在热路径 | 移到文件顶部 |
| H10 | response_builder.py:85 | O(n²) 字符串拼接 | 改用 list + join |
| H11 | streaming.py:66 | 首 chunk 超时后线程泄漏 | 加 is_alive 检查 + 日志 |

### 架构类

| # | 问题 | 修复方向 |
|---|------|---------|
| H12 | server.py 仍 15+ 处调用 smart_router | 逐步迁移到 V3 适配器 |
| H13 | server.py 2000+ 行 | 拆为 6 个模块 |

---

## 四、MEDIUM 级问题

| # | 位置 | 问题 |
|---|------|------|
| M1 | server.py:654 | Anthropic Tier2 异常 error_code=None 绕过退避 |
| M2 | server.py:699 | Tier1 流式失败不记录 failure |
| M3 | server.py:237 | `_try_backend` 吞超时不更新健康 |
| M4 | health_tracker.py:229 | `get_scores()` 锁释放后算分 |
| M5 | probe_loop.py:71 | 探活异常被吞无法区分编程错误 |
| M6 | stats_collector.py:105 | 硬编码 Windows 绝对路径 |
| M7 | fallback_chain.py:4-6 | 3 个未使用 import |
| M8 | stats_collector.py:73 | 重复 import functools |
| M9 | server.py:984 | size 参数无验证 → DoS |
| M10 | server.py:248 | 明文 HTTP 地理查询 → MITM |
| M11 | semantic_cache.py:97 | 双层 API 无文档易混淆 |
| M12 | server.py:126 | `_record_fallback` 文件 I/O 错误被吞 |

---

## 五、修复优先级与计划

### Sprint 1: 安全加固（紧急，1-2小时）

| 任务 | 文件 | 改动量 |
|------|------|--------|
| 管理接口加认证 | server.py | 加 FastAPI Depends，~20行 |
| 图片 n 参数限制 | server.py | 1行 Field 约束 |
| size 参数验证 | server.py | 3行正则+clamp |
| XSS 修复 | server.py admin HTML | innerHTML→textContent |
| IP 格式验证 | server.py | 5行正则 |
| Cloudflare token 移除硬编码 | server.py | 改为纯 os.environ[] |

### Sprint 2: 并发修复（重要，1小时）

| 任务 | 文件 | 改动量 |
|------|------|--------|
| KeyPool 实例锁 | key_pool.py | 锁移入 __init__ |
| probe_loop 线程安全 | probe_loop.py | Event + 锁 |
| stats_collector 锁外查询 | stats_collector.py | 重构 record_request |

### Sprint 3: 静默失败修复（重要，1小时）

| 任务 | 文件 | 改动量 |
|------|------|--------|
| _real_stream_chunks 异常传播 | server.py:1591 | 3行 |
| _last_resort_call 加日志 | server.py:17 | 2行 |
| routing_engine force-try 加日志 | routing_engine.py:149 | 3行 |
| _try_backend 记录健康 | server.py:237 | 3行 |
| Tier1/Tier2 记录 failure | server.py:654,699 | 5行 |

### Sprint 4: 质量改进（中等，半天）

| 任务 | 文件 | 改动量 |
|------|------|--------|
| import random 移到顶部 | routing_engine.py | 2行 |
| O(n²) _split_sentences 改 list+join | response_builder.py | 10行 |
| streaming.py 线程泄漏处理 | streaming.py | 5行 |
| 移除未使用 import | fallback_chain.py | 3行 |
| 硬编码路径改相对路径 | stats_collector.py, fallback_chain.py | 5行 |

### Sprint 5: 架构重构（长期，2-3天）

| 任务 | 描述 |
|------|------|
| server.py 拆分 | 拆为 routes/chat.py, routes/anthropic.py, routes/admin.py 等 |
| smart_router 解耦 | 将 15 处 smart_router.* 调用迁移到 V3 适配器 |
| response_cleaner 独立 | 从 http_caller 拆出品牌清洗逻辑 |
| 健康状态持久化 | 重启后恢复学习到的健康数据 |

---

## 六、不修复的项（接受风险）

| 问题 | 原因 |
|------|------|
| get_scores() 锁释放后算分 | 最终一致性可接受，不影响正确性 |
| semantic_cache 双层 API | 功能正确，仅文档问题 |
| bytearray del[:n] O(n) | 实际 SSE chunk 很小，不构成瓶颈 |

---

## 七、执行原则

1. **安全优先**: Sprint 1 必须在部署前完成
2. **最小改动**: 每个修复独立可测试，不引入新抽象
3. **向后兼容**: 接口签名不变，内部实现升级
4. **可观测性**: 每个静默失败点加 WARNING 日志
5. **渐进式**: 架构重构分多次 PR，不一次性大改