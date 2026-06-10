# 模型准入评估报告（2026年6月）

> 生成日期：2026-06-11
> 数据来源：backends_registry.py、device_gateway/model_routing.py

---

## 一、模型清单

### Fast 层（低延迟、低算力）

| 模型名称 | 类型 | 提供方 | 成本等级 | 兼容设备 |
|---------|------|--------|---------|---------|
| scnet_ds_flash | DeepSeek Flash | 智算平台 | 免费 | 低/中/高 |
| ollama_scnet | Ollama 本地 | 本地 | 免费 | 中/高 |

### Balanced 层

| 模型名称 | 类型 | 提供方 | 成本等级 | 兼容设备 |
|---------|------|--------|---------|---------|
| scnet_ds_medium | DeepSeek Medium | 智算平台 | 低成本 | 中/高 |

### Quality 层

| 模型名称 | 类型 | 提供方 | 成本等级 | 兼容设备 |
|---------|------|--------|---------|---------|
| scnet_ds_strong | DeepSeek Strong | 智算平台 | 中等 | 高 |
| github_gpt4o | GPT-4o | GitHub Models | 免费（5000次/月） | 高（需 vision） |

### 扩展 Backend 池（30+）

按平台分：

| 平台 | 包含模型 | 特点 |
|------|---------|------|
| **OpenRouter Free** | deepseek-r1, qwen3-coder, llama-3.3-70b, nemotron, mistral-large | 免费但排队制，超时不保证 |
| **NVIDIA API** | nemotron-super-49b, qwen-coder-480b, mistral-large-675b | 企业级质量，需 API Key |
| **Groq** | llama-70b-versatile, qwen-32b, llama-4-scout | 低延迟推理，免费层有速率限制 |
| **Cerebras** | qwen-235b, gpt-oss-120b, llama3.1-8b | 超大规模模型，需 API Key |
| **GitHub Models** | gpt-4o-mini, gpt-5, o3-mini, o4-mini | 免费额度充足，支持 tool_calls |
| **本地** | longcat-web, unclose-hermes, unclose-qwen | 自托管，延迟最低但性能有限 |

---

## 二、能力评估

### 延迟表现（基于 timeout 配置）

| 层级 | P50 预期 | P95 预期 | timeout 配置 |
|------|---------|---------|-------------|
| Fast | <500ms | <2s | 10-30s |
| Balanced | 1-3s | 5-10s | 30s |
| Quality | 2-5s | 10-20s | 15-60s |
| OpenRouter Free | 5-30s | 60s+ | 45-60s |

### 稳定性评估

- **scnet 系列**：自建平台，稳定性高 ✅
- **GitHub Models**：免费层稳定但速率有限制 ✅/⚠️
- **OpenRouter Free**：排队等待，高峰期超时风险高 ❌
- **NVIDIA API**：企业级，稳定性好但非免费 ✅
- **Groq**：推理快，免费层有并发限制 ✅/⚠️
- **Cerebras**：质量好但偶有超时 ⚠️

### 配额与限制

| 模型 | 速率限制 | 并发限制 | 总调用限制 |
|------|---------|---------|-----------|
| scnet_ds 系列 | 无 | 无 | 无（自建） |
| github_gpt4o | 10 req/min | 10 | 5000次/月 |
| OpenRouter Free | 5 req/min | 3 | 无 |
| Groq Free | 30 req/min | 6 | 无 |
| Cerebras | 30 req/min | 5 | 无 |

---

## 三、准入建议

| 模型 | 建议 | 理由 |
|------|------|------|
| scnet_ds_flash | ✅ **立即准入** | 免费、低延迟、自建稳定 |
| ollama_scnet | ✅ **立即准入** | 本地运行零延迟 |
| scnet_ds_medium | ✅ **立即准入** | 均衡表现，无限制 |
| scnet_ds_strong | ✅ **立即准入** | 高质量能力，自建可控 |
| github_gpt4o | ⚠️ **条件准入** | 上限5000次/月，超限后降级 |
| github_gpt4o_mini | ⚠️ **条件准入** | 轻量版 GPT-4o，用于简单任务 |
| github_o3_mini | ⚠️ **条件准入** | 高推理能力，速率限制松 |
| Groq 系模型 | ⚠️ **条件准入** | 速度优，但免费层不稳定 |
| OpenRouter Free 系 | ❌ **暂不准入** | 超时不可控，仅作 fallback 候选 |
| NVIDIA API | ⚠️ **条件准入** | 高质量但需付费 |
| Cerebras | ⚠️ **条件准入** | 超大模型候选，稳定性待观察 |

---

## 四、路由层级建议

| 层级 | 主模型 | 备选 | 适用场景 |
|------|-------|------|---------|
| **Fast** | scnet_ds_flash | ollama_scnet → groq_llama8b | 低算力设备、延迟敏感（LED/震动马达） |
| **Balanced** | scnet_ds_medium | groq_qwen32b → scnet_ds_flash | 通用中等负载（文本写入） |
| **Quality** | scnet_ds_strong | github_gpt4o → cerebras_qwen235b | 高算力设备、复杂任务（SVG/矢量图/分析） |
| **Fallback** | 按 fast→balanced→quality 顺序降级 | 上游不可用时的容错路径 | |

### 路由决策规则

1. **能力过滤**：按 Device Capability（compute_level, memory_mb, supported_features）过滤 MODEL_REGISTRY
2. **失败排除**：排除 DeviceHistory 中 failed_backends
3. **偏好调整**：
   - `latency_sensitive=true` → Fast 层 +35% 权重
   - `quality_priority=speed` → 优先 Fast 层
   - `quality_priority=quality` → 优先 Quality 层
   - `cost_sensitivity=high` → 抑制 Quality 层
4. **偏好模型**：偏好权重 +3
5. **排序取最佳**：按权重降序，同权按 tier 优先级

---

## 五、后续行动

- [ ] 为已准入模型配置 API Key / Token
- [ ] 监控扩展模型的真实稳定性数据，决定是否提升准入等级
- [ ] OpenRouter Free 系模型稳定后重新评估准入
- [ ] 设定配额告警：GitHub Models 月消耗达 80% 时预警
