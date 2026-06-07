# OpenCode 工具调用修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 OpenCode 工具调用超时/失败问题，使工具调用 TTFB < 3s 且功能可用。

**Architecture:** 保持生产请求路径权威性，只修复 OpenCode 工具处理边缘。优先诊断根因，然后针对性修复，避免盲目改动。

**Tech Stack:** Python 3.10, FastAPI, httpx, OpenAI-compatible SSE, pytest.

---

## 问题现状

### 症状

| 环境 | 表现 | 日志 |
|------|------|------|
| 本地 | 超时 >60s | 无明确错误 |
| VPS | 错误 | 未查看 |

### 已知线索

1. **配置疑点**：
   - `LIMA_OPENCODE_TOOL_MODE=direct` 是否生效？
   - `OPENCODE_TOOL_STABLE_BACKENDS` 是否包含当前后端？
   - `OPENCODE_DIRECT_STREAM_READ_TIMEOUT=180s` 是否生效？

2. **代码疑点**：
   - `routes/opencode_direct_stream.py` 的工具处理逻辑
   - Text-tool 转换可能有死循环或阻塞
   - 工具 schema 过大导致后端拒绝

3. **测试代码疑点**：
   - httpx 客户端超时 60s 可能太短
   - 测试用的工具 schema 可能触发特殊路径

---

## Task 1: 诊断根因

**目标**: 通过日志和代码审查找到确切失败点

### Step 1.1: 查看 VPS 错误日志

- [ ] SSH 到 VPS，查看最近的工具调用请求日志
  ```bash
  ssh vps "journalctl -u lima-router --since '10 minutes ago' | grep -E 'tool|opencode|error' -A 3 -B 3"
  ```

- [ ] 检查是否有明确的错误栈或超时日志

**预期输出**: 具体的错误类型（timeout / 400 / 500 / backend rejection）

---

### Step 1.2: 验证 VPS OpenCode 配置

- [ ] 读取 VPS `.env` 文件中的 OpenCode 相关配置
  ```bash
  ssh vps "cd /opt/lima-router && cat .env | grep OPENCODE"
  ```

- [ ] 对比期望配置：
  ```
  LIMA_OPENCODE_TOOL_MODE=direct
  LIMA_OPENCODE_DIRECT_STREAM=1
  LIMA_OPENCODE_DIRECT_STREAM_READ_TIMEOUT=180
  LIMA_OPENCODE_PREFERRED_BACKEND=scnet_ds_pro  # 或 groq
  LIMA_OPENCODE_TOOL_STABLE_BACKENDS=scnet_ds_pro,scnet_ds_flash,scnet_qwen235b,scnet_qwen30b
  ```

- [ ] 如配置缺失或错误，记录差异

**预期输出**: 配置差异清单

---

### Step 1.3: 审查工具处理代码路径

- [ ] 读取 `routes/opencode_direct_stream.py`，找到工具调用处理入口
  ```python
  # 重点关注：
  # 1. 工具 schema 如何传递给后端
  # 2. text-tool 转换逻辑在哪里触发
  # 3. 超时配置在哪里设置
  ```

- [ ] 读取 `opencode_text_tool_payload.py`（如果存在），检查转换逻辑

- [ ] 检查是否有同步阻塞操作（如大循环、同步 HTTP 调用）

**预期输出**: 代码审查笔记，标注可疑点

---

### Step 1.4: 本地复现并增加调试日志

- [ ] 在 `routes/opencode_direct_stream.py` 的工具处理路径增加日志：
  ```python
  _log.info(f"[opencode-tool] request has {len(req.tools)} tools")
  _log.info(f"[opencode-tool] backend={backend}, mode={OPENCODE_TOOL_MODE}")
  _log.info(f"[opencode-tool] starting backend call...")
  # 在后端调用后
  _log.info(f"[opencode-tool] backend call completed in {elapsed}ms")
  ```

- [ ] 本地启动服务，重新运行工具调用测试

- [ ] 观察日志，定位卡住的位置

**预期输出**: 日志显示卡在哪一步（路由决策 / 后端调用 / 响应解析）

---

## Task 2: 针对性修复

**根据 Task 1 的诊断结果，选择对应的修复方案**

### 方案 A: 配置问题

**适用于**: VPS 配置缺失或错误

- [ ] **Step 2A.1**: 在 VPS `.env` 中补充正确配置

- [ ] **Step 2A.2**: 重启服务
  ```bash
  ssh vps "systemctl restart lima-router"
  ```

- [ ] **Step 2A.3**: 重新运行性能测试验证

**验收**: 工具调用 TTFB < 3s，功能可用

---

### 方案 B: 后端不兼容

**适用于**: 当前后端不在 `TOOL_STABLE_BACKENDS` 中或不支持工具

- [ ] **Step 2B.1**: 检查当前后端是否支持工具调用
  ```python
  # 在 backends/ 中查找当前后端定义
  # 检查 supports_tools 或类似标记
  ```

- [ ] **Step 2B.2**: 如不支持，修改路由逻辑：
  ```python
  # 在 routing_engine.py 中
  if request.has_tools and not backend.supports_tools:
      # 强制切换到 TOOL_STABLE_BACKENDS[0]
      backend = get_backend(OPENCODE_TOOL_STABLE_BACKENDS[0])
  ```

- [ ] **Step 2B.3**: 添加测试用例验证路由切换

**验收**: 工具请求自动路由到兼容后端

---

### 方案 C: Text-tool 转换超时

**适用于**: 日志显示卡在 text-tool 转换步骤

- [ ] **Step 2C.1**: 读取 `opencode_text_tool_payload.py` 找到转换逻辑

- [ ] **Step 2C.2**: 检查是否有大循环或递归

- [ ] **Step 2C.3**: 优化转换逻辑：
  - 增加转换超时保护（如 5s）
  - 简化工具 schema（只保留必要字段）
  - 缓存转换结果

- [ ] **Step 2C.4**: 添加单元测试覆盖转换逻辑

**验收**: 转换耗时 < 100ms

---

### 方案 D: 后端超时

**适用于**: 后端调用本身超时

- [ ] **Step 2D.1**: 检查 `OPENCODE_DIRECT_STREAM_READ_TIMEOUT` 是否生效
  ```python
  # 在 routes/opencode_direct_stream.py 中
  timeout = httpx.Timeout(
      connect=10.0,
      read=OPENCODE_DIRECT_STREAM_READ_TIMEOUT,
      write=10.0,
      pool=10.0,
  )
  ```

- [ ] **Step 2D.2**: 如未生效，显式设置超时

- [ ] **Step 2D.3**: 增加超时后的 fallback 逻辑：
  ```python
  try:
      response = await call_backend(backend, request, timeout=180)
  except httpx.ReadTimeout:
      _log.warning(f"Backend {backend} timeout, trying fallback...")
      fallback_backend = get_fallback_backend()
      response = await call_backend(fallback_backend, request, timeout=60)
  ```

**验收**: 超时自动 fallback，用户无感知

---

### 方案 E: 测试代码问题

**适用于**: 测试用的工具 schema 不合理

- [ ] **Step 2E.1**: 简化测试工具 schema，去掉复杂嵌套

- [ ] **Step 2E.2**: 增加测试超时到 180s：
  ```python
  async with httpx.AsyncClient(timeout=180.0) as client:
      ...
  ```

- [ ] **Step 2E.3**: 使用真实 OpenCode 工具 schema 测试（如 `read_file`）

**验收**: 测试通过，TTFB < 3s

---

## Task 3: 优化和验证

**在修复后进行优化和全面验证**

### Step 3.1: 增加工具调用专用 fast-path

- [ ] 在 `routes/opencode_direct_stream.py` 中增加工具调用快速路径：
  ```python
  if request.has_tools and is_opencode_client:
      # 跳过不必要的中间件
      # 直接路由到 TOOL_STABLE_BACKENDS[0]
      # 使用预编译的工具 schema
  ```

- [ ] 测量优化后的 TTFB

**目标**: TTFB < 2s（优于 3s 目标）

---

### Step 3.2: 本地全面测试

- [ ] 运行完整的性能测试套件：
  ```bash
  pytest tests/test_opencode_performance.py -v
  ```

- [ ] 验证：
  - 纯文本 TTFB < 2s
  - 工具调用 TTFB < 3s
  - TPS > 20

**预期**: 所有测试通过

---

### Step 3.3: VPS 验证

- [ ] 部署修复代码到 VPS：
  ```bash
  python scripts/deploy_unified.py --files routes/opencode_direct_stream.py opencode_text_tool_payload.py
  ```

- [ ] 在 VPS 上重新运行性能检查：
  ```bash
  ssh vps "cd /opt/lima-router && python3 scripts/vps_performance_check.py"
  ```

- [ ] 验证工具调用测试通过

**预期**: VPS 测试 2 passed, 1 可能仍未达标（纯文本 TTFB）

---

### Step 3.4: 真实 OpenCode CLI 端到端测试

- [ ] 在本地用 OpenCode CLI 连接 VPS

- [ ] 执行真实工具调用命令：
  ```bash
  opencode run --model lima/lima-1.3 "read the file server.py and summarize"
  ```

- [ ] 观察：
  - 响应时间
  - 工具调用是否成功
  - 工具结果是否正确

**预期**: CLI 正常工作，用户体验流畅

---

## Task 4: 文档和记忆

### Step 4.1: 更新性能基线报告

- [ ] 在 `docs/vps-performance-baseline.md` 中添加修复后的数据

- [ ] 对比修复前后的改进

---

### Step 4.2: 创建记忆文档

- [ ] 如发现新的陷阱或最佳实践，写入记忆：
  ```markdown
  ---
  name: opencode-tool-call-timeout-fix
  description: OpenCode 工具调用超时的根因和修复方法
  metadata:
    type: feedback
  ---
  
  ## 问题
  ...
  
  ## 根因
  ...
  
  ## 修复方法
  ...
  ```

---

### Step 4.3: 更新优化计划

- [ ] 在 `docs/superpowers/plans/2026-06-07-opencode-deep-optimization.md` 中：
  - 标记 Task 1（性能基线）为完成
  - 更新工具调用相关任务状态
  - 添加实测数据

---

## 验收标准

修复完成后，应达到：

### 功能性
- ✅ 工具调用请求能正常返回（不超时、不报错）
- ✅ 工具 schema 正确传递给后端
- ✅ 工具响应正确解析和返回

### 性能
- ✅ 工具调用 TTFB < 3s（目标）
- ✅ 工具调用 TTFB < 2s（优化目标）

### 稳定性
- ✅ 本地测试 100% 通过
- ✅ VPS 测试 100% 通过
- ✅ 真实 OpenCode CLI 端到端测试通过

### 可维护性
- ✅ 增加了充分的日志
- ✅ 增加了错误处理和 fallback
- ✅ 文档和记忆更新

---

## 执行顺序

1. **Task 1（诊断）** → 必须先明确根因
2. **Task 2（修复）** → 根据诊断结果选择方案
3. **Task 3（验证）** → 本地 + VPS + 真实 CLI
4. **Task 4（文档）** → 记录和分享

**预计时间**: 3-4 小时（诊断 1h + 修复 1-2h + 验证 1h）

**优先级**: P0 - 阻塞 OpenCode 核心功能
