# OpenCode 深度联调优化计划

## 背景

OpenCode E2E 适配和运行时优化已完成（见 `docs/superpowers/plans/2026-06-07-*.md`），基础功能已验证通过。现需要针对**真实使用场景**进行深度联调，优化体验瓶颈。

## 当前状态评估

### ✅ 已完成的工作

1. **OpenCode CLI E2E 适配**
   - OpenAI SSE 兼容性
   - 工具调用直通模式
   - 空流回退机制
   - 真实 CLI 会话验证通过

2. **VPS 运行时优化**
   - 工具意图门控（纯文本请求不注入工具提示）
   - 文本工具后端分离（`OPENCODE_TOOL_STABLE_BACKENDS`）
   - 默认后端优化（`scnet_ds_pro`）
   - 生产环境验证通过

### 🔍 待深度优化的场景

基于 OpenCode 实际使用模式，以下场景需要优化：

| 场景 | 当前状态 | 优化目标 |
|------|---------|---------|
| **首次响应延迟（TTFB）** | 未测量 | < 2s（纯文本），< 3s（工具调用） |
| **大文件工具输出** | 可能截断 | 支持 10K+ 行文件读取 |
| **多轮工具调用链** | 未测试 | 5+ 轮不掉链 |
| **并发请求稳定性** | 未压测 | 10 并发不降级 |
| **长会话上下文管理** | 自动压缩 | 20+ 轮对话不溢出 |
| **错误恢复体验** | 基础 fallback | 用户无感知的透明重试 |

---

## 优化任务清单

### Task 1: 性能基线测量

**目标**: 建立当前性能指标基线，识别瓶颈

**Steps:**

- [ ] **Step 1.1: 编写性能测试套件**
  
  创建 `tests/test_opencode_performance.py`，测量：
  - TTFB（Time To First Byte）：首字节延迟
  - TTFT（Time To First Token）：首个有效 token 延迟
  - TPS（Tokens Per Second）：流式输出速率
  - Tool latency：工具调用往返延迟

  ```python
  @pytest.mark.asyncio
  async def test_ttfb_plain_text():
      """测量纯文本请求的首字节延迟"""
      start = time.time()
      async with httpx.AsyncClient() as client:
          async with client.stream(...) as response:
              first_chunk = await anext(response.aiter_bytes())
              ttfb = time.time() - start
      assert ttfb < 2.0, f"TTFB {ttfb:.2f}s exceeds 2s target"
  ```

- [ ] **Step 1.2: 本地基线测量**
  
  在本地环境（`127.0.0.1:8090`）运行测试，记录：
  - 纯文本请求 TTFB
  - 工具调用请求 TTFB
  - 5 轮对话的累计延迟
  - 内存占用趋势

- [ ] **Step 1.3: VPS 基线测量**
  
  在生产环境（`https://chat.donglicao.com`）重复测量，对比：
  - 网络延迟影响（RTT）
  - VPS 负载影响
  - 识别性能退化点

**产出**: `docs/opencode-performance-baseline.md`，包含表格化的性能指标和瓶颈分析

---

### Task 2: 大文件工具输出优化

**目标**: 支持读取和返回大文件（10K+ 行）而不截断或超时

**Steps:**

- [ ] **Step 2.1: 测试当前大文件边界**
  
  创建测试文件（1K/5K/10K/20K 行），用 OpenCode `/read` 命令测试：
  - 哪个大小开始截断？
  - 是否触发 timeout？
  - 工具输出是否完整传回？

- [ ] **Step 2.2: 识别截断点**
  
  检查：
  - `opencode_config.py` 的 `OPENCODE_DIRECT_STREAM_READ_TIMEOUT`（当前 180s）
  - `routes/opencode_direct_stream.py` 的响应大小限制
  - 下游后端的 token 限制（`scnet_ds_pro` 的输出限制）

- [ ] **Step 2.3: 实现分块传输或流式工具输出**
  
  如果工具输出过大，考虑：
  - 方案 A: 工具输出分段（前 5K 行 + "... truncated, use /read --lines 5000-10000"）
  - 方案 B: 流式工具调用（OpenAI 新特性，需验证 OpenCode 支持度）
  - 方案 C: 增加后端超时和输出限制

**产出**: 大文件支持方案文档 + 测试用例

---

### Task 3: 多轮工具调用链稳定性

**目标**: 5+ 轮工具调用不掉链、不重复、不遗漏

**Steps:**

- [ ] **Step 3.1: 设计多轮工具链测试场景**
  
  典型场景：
  1. **搜索 → 读取 → 编辑 → 验证** (4 轮)
  2. **列目录 → 读多文件 → 对比 → 总结** (5 轮)
  3. **执行命令 → 读日志 → 修复 → 重试** (4+ 轮，可能循环)

- [ ] **Step 3.2: 验证工具调用 ID 持久性**
  
  检查：
  - `tool_call_id` 是否正确传递和响应
  - OpenCode 是否正确关联 tool response
  - LiMa 是否保持 tool call context

- [ ] **Step 3.3: 测试工具调用错误恢复**
  
  模拟场景：
  - 工具返回错误（如文件不存在）
  - 工具超时
  - 后端拒绝工具调用
  
  验证 OpenCode 能正确继续或重试

**产出**: 多轮工具链测试套件 + 稳定性报告

---

### Task 4: 并发请求稳定性

**目标**: 10 并发 OpenCode 会话不相互干扰、不资源耗尽

**Steps:**

- [ ] **Step 4.1: 编写并发测试脚本**
  
  ```python
  async def simulate_opencode_session(session_id: int):
      """模拟一个 OpenCode 会话：对话 → 工具调用 → 继续对话"""
      # 5 轮对话，包含 2 次工具调用
      ...
  
  async def test_concurrent_sessions():
      tasks = [simulate_opencode_session(i) for i in range(10)]
      results = await asyncio.gather(*tasks, return_exceptions=True)
      assert all(r.success for r in results if not isinstance(r, Exception))
  ```

- [ ] **Step 4.2: 本地并发压测**
  
  测量：
  - 成功率（10/10）
  - 平均延迟增长（vs 单请求）
  - 内存峰值
  - 是否有连接池耗尽

- [ ] **Step 4.3: VPS 并发压测**
  
  在生产环境重复，识别：
  - VPS CPU/内存瓶颈
  - 后端 rate limit 触发
  - 连接池配置是否合理

**产出**: 并发性能报告 + 配置优化建议

---

### Task 5: 长会话上下文管理

**目标**: 20+ 轮对话不溢出，压缩策略对 OpenCode 友好

**Steps:**

- [ ] **Step 5.1: 测试当前上下文压缩行为**
  
  创建 20 轮对话（混合纯文本和工具调用），观察：
  - 何时触发压缩？
  - 压缩后保留多少轮？（当前 `OPENCODE_KEEP_RECENT_TURNS=8`）
  - 工具调用结果是否被错误压缩掉？

- [ ] **Step 5.2: 优化 OpenCode 专属压缩策略**
  
  建议：
  - 工具调用轮必须保留（避免丢失上下文）
  - System message 保留（OpenCode 注入的指令）
  - 普通对话可以更激进压缩

- [ ] **Step 5.3: 测试溢出错误处理**
  
  故意触发溢出（超长对话），验证：
  - LiMa 返回清晰的 413 / overflow SSE event
  - OpenCode 正确显示错误信息
  - 用户知道如何恢复（`/clear`）

**产出**: 上下文管理优化方案 + 溢出处理文档

---

### Task 6: 错误恢复体验优化

**目标**: 后端失败时自动 fallback，用户无感知

**Steps:**

- [ ] **Step 6.1: 测试当前 fallback 行为**
  
  模拟场景：
  - 首选后端 `scnet_ds_pro` 不可用
  - 第二选择 `scnet_ds_flash` 也失败
  - 所有 OPENCODE_TOOL_STABLE_BACKENDS 都失败

  验证：
  - 是否自动切换到其他后端？
  - 切换是否透明（无中断）？
  - 工具调用是否在切换后仍然工作？

- [ ] **Step 6.2: 优化 fallback 链**
  
  检查 `OPENCODE_TOOL_STABLE_BACKENDS` 顺序：
  - 是否按照可靠性/速度排序？
  - 是否包含足够的备选（当前 4 个）？
  - 是否需要动态调整（根据健康检查）？

- [ ] **Step 6.3: 增强错误消息**
  
  确保错误消息对用户友好：
  - "Backend temporarily unavailable, retrying..."（而非原始 API 错误）
  - 明确告知是暂时性错误还是配置问题
  - 提供 troubleshooting 链接或建议

**产出**: Fallback 链优化 + 错误消息改进

---

## 验收标准

完成本计划后，OpenCode + LiMa 应达到：

### 性能指标

- ✅ **TTFB < 2s**（纯文本）
- ✅ **TTFB < 3s**（工具调用）
- ✅ **TPS > 20 tokens/s**（流式输出）
- ✅ **10 并发成功率 > 95%**

### 功能稳定性

- ✅ **支持 10K 行文件读取**
- ✅ **5 轮工具链 100% 成功**
- ✅ **20 轮对话不溢出**
- ✅ **后端故障透明 fallback**

### 用户体验

- ✅ **错误消息清晰易懂**
- ✅ **溢出后知道如何恢复**
- ✅ **无感知的性能优化**

---

## 执行顺序建议

1. **Task 1（性能基线）** → 先了解现状
2. **Task 4（并发稳定性）** → 验证基础架构稳定
3. **Task 3（工具链稳定性）** → OpenCode 核心场景
4. **Task 5（上下文管理）** → 长期使用体验
5. **Task 2（大文件优化）** → 特定痛点
6. **Task 6（错误恢复）** → 最终兜底

---

**预计时间**: 2-3 天（每个 Task 4-6 小时）

**优先级**: Task 1 和 Task 4 为 P0（基础稳定性），其他为 P1（体验优化）
