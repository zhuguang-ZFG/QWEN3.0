# UncloseAI 免费后端集成方案

> 状态：✅ 完成 | 创建：2026-05-19

## 背景

[uncloseai.com](https://uncloseai.com/) 提供免费、无需 API Key 的 OpenAI 兼容端点。
适合作为 LiMa 路由系统的 L1 免费后端补充，增加冗余和降低对单一供应商的依赖。

## 可用端点

| 端点 | Base URL | 模型 | 用途 |
|------|----------|------|------|
| Hermes | `https://hermes.ai.unturf.com/v1/chat/completions` | hermes | 通用对话 |
| Qwen Coder | `https://qwen.ai.unturf.com/v1/chat/completions` | qwen3-coder | 代码生成 |
| TTS | `https://speech.ai.unturf.com/v1` | - | 语音合成（暂不集成） |

## 集成规格

### 后端配置

```python
# smart_router.py BACKENDS 新增
'unclose_hermes': {
    'url': 'https://hermes.ai.unturf.com/v1/chat/completions',
    'key': 'none',
    'model': 'hermes',
    'fmt': 'openai',
    'timeout': 30,
},
'unclose_qwen': {
    'url': 'https://qwen.ai.unturf.com/v1/chat/completions',
    'key': 'none',
    'model': 'qwen3-coder',
    'fmt': 'openai',
    'timeout': 30,
},
```

### Fallback Chain 位置

放在 L1 免费层（与 LongCat、中国移动同级）：

| 意图 | 插入位置 | 后端 |
|------|----------|------|
| code_generation | nvidia_qwen_coder 之后 | unclose_qwen |
| general_cnc | longcat_chat 之后 | unclose_hermes |
| trivial | nvidia_phi4 之后 | unclose_hermes |
| architecture | longcat 之后 | unclose_hermes |

### 特殊处理

1. **无 API Key**：`key: 'none'` — 需确保 `call_api()` 和 `call_api_stream()` 对 `key='none'` 正常发送请求（当前逻辑检查 `b['key']` 为 truthy）
2. **Authorization Header**：无需认证头，或发送空 Bearer token
3. **Model Discovery**：首次连接时查询 `/v1/models` 确认实际 model ID

## 执行步骤

### Step 1: 连通性测试（不改代码）

```bash
# 测试 Hermes
curl -s -X POST https://hermes.ai.unturf.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes","messages":[{"role":"user","content":"hi"}],"max_tokens":20}'

# 测试 Qwen Coder
curl -s -X POST https://qwen.ai.unturf.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-coder","messages":[{"role":"user","content":"def hello():"}],"max_tokens":50}'

# 测试流式
curl -s -N -X POST https://hermes.ai.unturf.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes","messages":[{"role":"user","content":"hi"}],"stream":true,"max_tokens":20}'

# Model Discovery
curl -s https://hermes.ai.unturf.com/v1/models
curl -s https://qwen.ai.unturf.com/v1/models
```

### Step 2: 添加后端配置

修改 `smart_router.py` BACKENDS dict，添加两个新后端。

### Step 3: 修复 key='none' 兼容性

当前 `call_api()` 检查 `if not b or not b['key']` 会拒绝空 key。
需要对 `key='none'` 做特殊处理：视为"无需认证"。

### Step 4: 更新 Fallback Chains

将新后端插入对应意图的降级链。

### Step 5: 集成测试

通过 LiMa 路由系统发送请求，验证：
- 非流式调用正常
- 流式调用正常
- 熔断器正常记录
- 延迟排序正常工作

## 验收标准

- [x] 两个端点连通性测试通过（Hermes 1.2s, Qwen 3s）
- [x] 流式和非流式都正常（Hermes 流式确认逐 token）
- [x] 集成到 fallback chain 后路由正常（backend: unclose_hermes）
- [x] 熔断器对新后端正常工作
- [x] 延迟数据正常记录（6253ms via LiMa routing）

## 实际 Model ID（通过 /v1/models 发现）

| 端点 | 实际 Model ID | 引擎 |
|------|--------------|------|
| Hermes | `adamo1139/Hermes-3-Llama-3.1-8B-FP8-Dynamic` | vLLM |
| Qwen | `Qwen3.6-27B-UD-Q4_K_XL.gguf` | llama.cpp |

## 注意事项

- Qwen 端点对复杂问题响应较慢（>15s），适合作为 fallback 而非首选
- Hermes 端点快速稳定（1.2s 直连，6.2s 经 LiMa 路由）
- 无需 API Key，`key: 'none'` 发送 `Bearer none` 头，vLLM/llama.cpp 忽略
