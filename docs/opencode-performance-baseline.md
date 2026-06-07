# OpenCode 性能基线报告

**测试日期**: 2026-06-07  
**测试环境**: Windows 本地开发环境（`127.0.0.1:8090`）  
**后端配置**: `LIMA_OPENCODE_PREFERRED_BACKEND=scnet_ds_pro`

---

## 测试结果摘要

| 指标 | 实际值 | 目标值 | 状态 |
|------|--------|--------|------|
| **TTFB（纯文本）** | 5137.9ms | < 2000ms | ❌ **2.6x 超标** |
| **TTFB（工具调用）** | >60000ms（超时） | < 3000ms | ❌ **20x+ 超标** |
| **TPS（流式输出）** | 44.94 tokens/s | > 20 tokens/s | ✅ **达标（2.2x）** |
| **多轮对话延迟** | 未测试 | < 15s (5轮) | - |
| **并发稳定性** | 未测试 | > 95% | - |

---

## 详细测试数据

### 1. TTFB 纯文本请求

**请求**: `Say OK`  
**结果**:
```json
{
  "ttfb_ms": 5137.9,
  "ttft_ms": 5137.9,
  "total_ms": 5206.55,
  "token_count": 2,
  "chunk_count": 1,
  "tps": 0.38
}
```

**分析**:
- ❌ 首字节延迟 **5.1 秒**，远超 2 秒目标
- ⚠️ 首个有效 token 和首字节同时到达，说明没有流式输出
- ⚠️ 只有 1 个 chunk，整个响应是一次性返回的
- ⚠️ TPS 0.38 tokens/s 极低（总共才 2 个 token）

**可能原因**:
1. **后端冷启动**：首次请求可能触发后端初始化
2. **路由延迟**：智能路由决策耗时过长
3. **后端响应慢**：`scnet_ds_pro` 可能负载高或地理位置远
4. **非流式返回**：后端可能返回的是非流式响应

---

### 2. TTFB 工具调用请求

**请求**: `List files in current directory`（带 `list_files` 工具定义）  
**结果**: ❌ **超时（> 60 秒）**

**分析**:
- ❌ 工具调用请求完全超时，无法获得响应
- ⚠️ 可能原因：
  1. 工具模式配置问题（text-tool 转换耗时）
  2. 后端不支持工具调用导致挂起
  3. 路由到错误的后端（非工具兼容后端）

---

### 3. 流式输出 TPS

**请求**: `Write a 200-word paragraph about coding`  
**结果**:
```json
{
  "ttfb_ms": null,
  "ttft_ms": null,
  "total_ms": 11794.07,
  "token_count": 530,
  "chunk_count": 1,
  "tps": 44.94
}
```

**分析**:
- ✅ TPS 44.94 tokens/s **超过目标 2 倍**，性能优秀
- ❌ 但 `ttfb_ms` 和 `ttft_ms` 都是 `null`，说明**没有记录到首字节**
- ⚠️ 只有 1 个 chunk，但 token_count=530，说明：
  - 响应是流式的（总时长 11.8s）
  - 但测试代码可能没正确捕获首个 chunk 的时间
  - 或者后端一次性返回了整段文本

**结论**: 一旦开始传输，速度是可以的，但启动延迟可能仍然存在

---

## 关键问题识别

### 🔴 P0 问题：TTFB 过高（5+ 秒）

**影响**: 用户等待时间长，体验差

**可能根因**:
1. **路由层延迟**
   - 智能路由决策算法复杂度高
   - 健康检查耗时
   - 后端选择逻辑有同步阻塞

2. **后端冷启动**
   - 第一次请求触发模型加载
   - 连接池未预热
   - DNS 解析延迟

3. **配置问题**
   - `scnet_ds_pro` 可能不是最快的选择
   - 未启用合适的缓存策略
   - 预热机制缺失

**优化方向**:
- [ ] 测试其他快速后端（`groq_`, `cerebras_`, `kimi`）
- [ ] 增加路由缓存（session affinity）
- [ ] 预热连接池和健康检查
- [ ] 分析路由决策耗时（增加日志）

---

### 🔴 P0 问题：工具调用超时（> 60s）

**影响**: OpenCode 核心功能不可用

**可能根因**:
1. **工具模式配置错误**
   - `LIMA_OPENCODE_TOOL_MODE=direct` 可能未生效
   - Text-tool 转换逻辑有死循环
   - 工具 schema 过大导致后端拒绝

2. **后端不兼容**
   - `scnet_ds_pro` 可能不在 `OPENCODE_TOOL_STABLE_BACKENDS` 中
   - 路由到了不支持工具的后端
   - 工具响应格式不匹配导致挂起

3. **超时配置**
   - `OPENCODE_DIRECT_STREAM_READ_TIMEOUT=180s` 未生效
   - httpx 客户端超时设置为 60s

**优化方向**:
- [ ] 检查 `opencode_config.py` 实际生效的配置
- [ ] 验证 `OPENCODE_TOOL_STABLE_BACKENDS` 是否包含当前后端
- [ ] 增加工具调用专用路由路径
- [ ] 添加工具调用超时保护和 fallback

---

### 🟡 P1 问题：流式输出不稳定

**影响**: 响应延迟感知不一致

**观察**:
- 纯文本请求：只有 1 个 chunk（非流式）
- 长文本请求：正常流式（44.94 TPS）

**可能原因**:
- 短文本被缓存或后端一次性返回
- SSE 事件合并策略
- 测试代码的计量逻辑问题

**优化方向**:
- [ ] 统一流式策略（即使短文本也流式返回）
- [ ] 优化 SSE 事件发送频率
- [ ] 确认测试代码正确性

---

## 对比目标差距

| 指标 | 实测 | 目标 | 差距 |
|------|------|------|------|
| TTFB（纯文本） | 5.1s | 2.0s | **-3.1s** |
| TTFB（工具） | >60s | 3.0s | **-57s+** |
| TPS | 44.9 | 20 | **+24.9** ✅ |

**总体评估**: 
- ❌ **不可接受** — 核心延迟指标远超目标
- ✅ 流式速度优秀（一旦开始传输）
- 🔧 需要紧急优化路由和工具调用路径

---

## 下一步行动

### 立即执行（今天）

1. **诊断 TTFB 瓶颈**
   - 在服务器日志中添加路由决策时间戳
   - 测试不同后端的 TTFB（groq, cerebras, kimi）
   - 确认是路由慢还是后端慢

2. **修复工具调用超时**
   - 检查 `opencode_direct_stream.py` 的工具处理逻辑
   - 验证 `OPENCODE_TOOL_STABLE_BACKENDS` 配置
   - 增加超时保护和错误日志

3. **快速验证优化效果**
   - 切换到 `groq_llama3370b` 或 `kimi` 重测
   - 如果 TTFB < 2s，说明是后端选择问题
   - 如果仍然慢，说明是路由层问题

### 短期目标（本周）

4. **实现路由缓存**
   - Session affinity 自动生效
   - 减少重复的健康检查

5. **优化工具调用路径**
   - 专用的 fast-path 跳过不必要的中间件
   - 预编译工具 schema

6. **完成全套性能测试**
   - 多轮对话延迟
   - 并发稳定性
   - 长会话上下文管理

---

## 附录：测试环境信息

**LiMa 配置**:
```
LIMA_OPENCODE_TOOL_MODE=direct
LIMA_OPENCODE_DIRECT_STREAM=1
LIMA_OPENCODE_DIRECT_STREAM_READ_TIMEOUT=180
LIMA_OPENCODE_PREFERRED_BACKEND=scnet_ds_pro
LIMA_OPENCODE_TOOL_STABLE_BACKENDS=scnet_ds_pro,scnet_ds_flash,scnet_qwen235b,scnet_qwen30b
```

**测试客户端**: httpx AsyncClient, timeout=60s  
**测试方法**: SSE 流式解析，逐行处理 `data:` 事件  
**测试脚本**: `tests/test_opencode_performance.py`
