# 编程模型塔生产就绪差距分析 — 头脑风暴

> 日期: 2026-05-22
> 状态: 分析完成，待执行
> 原则: 先诊断再动手，避免无效劳动

---

## 一、当前状态诊断

编程模型塔 V3 已部署，但实际生产覆盖率接近 0%。

### 流量覆盖分析



---

## 二、P0 阻塞点（不解决等于没部署）

### 2.1 Streaming 不兼容

问题:
  server.py 的 streaming 路径 (stream=true) 完全绕过 routing_engine.route()
  直接调用后端并 yield SSE chunks
  orchestrator 的质量门、修复、信誉分全部失效

影响: 90% 的请求不经过任何质量保障

可选方案:

| 方案 | 首 token 延迟 | 质量保障 | 改动量 | 适用层 |
|------|-------------|---------|--------|--------|
| A: 全缓冲后流式 | +5-15s | 完整(门+修复) | 中 | Complex |
| B: 直接流式+后置统计 | 0 | 仅统计不拦截 | 小 | Simple |
| C: 只选后端+注入上下文 | 0 | 上下文增强 | 小 | 全层 |
| D: 分层混合 A+B+C | 按层不同 | 按层不同 | 大 | 最终目标 |

推荐路径:
  第一步: 方案 C (零延迟，只做上下文增强和后端选择)
  第二步: 方案 D (分层，Simple 直接流，Complex 缓冲验证)

方案 C 的核心思路:
  orchestrator 不做质量门和修复（这些阻塞响应）
  只做三件零延迟的事:
    1. 语言检测 -> 精准规范注入
    2. 意图增强
    3. 按信誉分选最优后端
  质量门改为后置: 响应完成后异步评分，更新信誉分
  用户无感知延迟，但后端选择越来越准

### 2.2 call_fn 对接未验证

问题:
  orchestrator 期望: call_fn(backend_name, messages, max_tokens) -> str
  server.py 实际传入的 call_fn 是什么？签名是否匹配？
  生产测试超时说明可能不匹配或后端全部失败

需要确认:
  - server.py 在哪里构造 call_fn 并传给 routing_engine.route()
  - call_fn 内部是否正确调用了 http_caller
  - 超时设置是否合理（orchestrator 内部无单次调用超时）
  - 后端名是否与 POOLS 中的完全匹配

### 2.3 后端池名与实际配置不匹配风险

问题:
  POOLS 硬编码了后端名:
    fast: [groq_gptoss, cerebras_gptoss, groq_llama4, longcat_lite]
    coder: [cf_qwen_coder, mistral_codestral, nvidia_qwen_coder, groq_llama70b]
    strong: [cf_deepseek_r1, github_gpt4o, sambanova_ds_v3]

  这些名字是否与 server.py 的 152 个后端配置完全一致？
  如果有一个名字拼错，整个池就失效，orchestrator 返回空 -> fallback

验证方法:
  读 server.py 的 backends 配置，逐一比对 POOLS 中的名字

---

## 三、P1 问题（做了才能迭代）

### 3.1 无可观测性

问题: 部署了但完全盲飞
  - 不知道 orchestrator 实际处理了多少请求
  - 不知道质量门通过率
  - 不知道哪些后端被降级
  - 不知道平均延迟
  - 不知道语言检测分布

需要:
  - 内存计数器 (tier/language/backend/gate_pass/repair)
  - /api/orchestrator-stats 端点暴露统计
  - 日志关键事件 (repair触发、冷却触发、全池耗尽)

### 3.2 与现有投机执行的关系

问题:
  routing_engine.py 原有 speculative.classify_complexity() + 投机执行
  现在 orchestrator 在它之前拦截 coding 请求
  如果 orchestrator 失败 (catch Exception pass)，请求 fallback 到旧逻辑

当前关系:
  orchestrator 成功 -> 返回结果（旧逻辑不执行）
  orchestrator 失败 -> 走旧逻辑（投机执行）

是否最优？
  可能不是。投机执行的 5 路竞速对 Simple 层很有效
  orchestrator 的 Simple 层只是顺序尝试 fast 池
  也许 Simple 层应该继续走投机执行，orchestrator 只处理 Standard/Complex

---

## 四、P2 问题（优化项）

### 4.1 质量门误判

误拒风险:
  - 合法的 eval() 被标记为 code_injection
  - 教学代码中的 password="example" 被标记为 hardcoded_secret
  - 短回答被标记为 too_short（有些问题确实只需要一行代码）

误放风险:
  - 逻辑错误但语法正确的代码通过所有检查
  - 非 Python 代码无法做 AST 检查
  - 算法错误（死循环、off-by-one）无法静态检测

### 4.2 修复 prompt 暴露用户代码

安全风险:
  修复路径把用户代码 + 错误原因发给 Strong 后端
  如果用户代码包含 API key、内部逻辑、商业秘密
  这些会被发送到第三方免费 API（无隐私保障）

缓解:
  - 修复前脱敏（替换疑似密钥为 [REDACTED]）
  - 或只发送错误描述，不发送完整代码

### 4.3 信誉分冷启动

问题: 服务重启后所有信誉分归零（纯内存）
  - 重启后前 N 个请求无法利用历史数据
  - 频繁重启（部署）导致信誉分永远不成熟

方案:
  - 简单: 每 5 分钟写入 JSON 文件，启动时加载
  - 复杂: Redis 持久化（过度工程）

### 4.4 意图模板误匹配

问题:
  - "我想 import 一个库" 可能匹配到 "文件读写" 模板
  - 简单问题被过度增强，反而让弱模型困惑
  - 模板匹配是贪婪的（第一个匹配就返回）

改进:
  - 多模板匹配时取最高置信度
  - 短查询（<50字）不做意图增强（避免过度工程化简单问题）

### 4.5 多语言混合请求

问题: "用 Python 调用这个 Rust FFI" 只检测到一种语言
改进: 检测主语言 + 辅助语言，注入两份规范

### 4.6 orchestrator 内部无单次调用超时

问题:
  _try_backends_ranked 中 call_fn(backend, msgs, max_tokens) 可能永远阻塞
  延迟预算只检查总时间，不限制单次调用
  一个慢后端可能吃掉整个预算

改进:
  call_fn 应该有单次超时（如 8s），超时立即尝试下一个

---

## 五、执行优先级



---

## 六、核心认知转变



---

## 七、与 Cursor Auto 的最终对齐




---

## 八、验证结果 (2026-05-22 执行)

### call_fn 对接: PASS



### 后端池名: PASS (11/11)

| Pool | Backend | 验证 |
|------|---------|------|
| fast | groq_gptoss | backends.py:35 |
| fast | cerebras_gptoss | backends.py:42 |
| fast | groq_llama4 | backends.py:38 |
| fast | longcat_lite | backends.py:10 |
| coder | cf_qwen_coder | backends.py:57 |
| coder | mistral_codestral | backends.py:72 |
| coder | nvidia_qwen_coder | backends.py:17 |
| coder | groq_llama70b | backends.py:34 |
| strong | cf_deepseek_r1 | backends.py:62 |
| strong | github_gpt4o | backends.py:43 |
| strong | sambanova_ds_v3 | backends.py:117 |

### Streaming 路径: BLOCKED



### 下一步执行项


