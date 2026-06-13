# qwen2API 支持的模型列表

**总计**: **156个模型** (包含各种模式变体)

---

## 📊 模型系列概览

| 系列 | 模型数量 | 特点 |
|------|---------|------|
| **Qwen3.7** | 16个 | 最新旗舰系列 (Plus/Max) |
| **Qwen3.6** | 34个 | 稳定版本 (Plus/Max-Preview/27B/35B) |
| **Qwen3.5** | 58个 | 丰富生态 (Plus/Flash/Omni/27B/35B/122B/397B) |
| **Qwen3** | 30个 | 基础系列 (Max/Coder/VL/Omni) |
| **Qwen** | 18个 | 经典系列 + Beta 版本 |

---

## 🎯 主要基础模型

### Qwen3.7 系列（最新）
- **qwen3.7-plus** - 高性能大语言模型，支持文本和多模态任务
- **qwen3.7-max** - 旗舰模型，业界领先性能（当前仅支持文本）

### Qwen3.6 系列
- **qwen3.6-plus** - 大语言模型，支持文本和多模态
- **qwen3.6-max-preview** - 旗舰预览版
- **qwen3.6-27b** - 27B 稠密模型，针对本地部署优化
- **qwen3.6-35b-a3b** - 35B A3B 变体

### Qwen3.5 系列
- **qwen3.5-plus** - 通用大语言模型
- **qwen3.5-flash** - 快速响应版本
- **qwen3.5-omni-plus** / **qwen3.5-omni-flash** - 全模态模型
- **qwen3.5-27b** - 27B 模型
- **qwen3.5-35b-a3b** - 35B A3B 变体
- **qwen3.5-122b-a10b** - 122B A10B 变体
- **qwen3.5-397b-a17b** - 397B A17B 超大模型
- **qwen3.5-max-2026-03-08** - Max 预览版

### Qwen3 系列
- **qwen3-max-2026-01-23** - 旗舰模型
- **qwen3-coder-plus** - 代码专用模型
- **qwen3-vl-plus** - 视觉语言模型
- **qwen3-omni-flash-2025-12-01** - 全模态快速版

### 经典系列
- **qwen-plus-2025-07-28** - Qwen3-235B-A22B-2507
- **qwen-latest-series-invite-beta-v24** - Qwen3.7-Max-Preview
- **qwen-latest-series-invite-beta-v16** - Qwen3.7-Plus-Preview
- **qwen3.6-plus-preview** - Qwen3.6-Plus-Preview

---

## 🔧 模型模式（Mode）

每个基础模型都支持多种模式，例如：

| 模式 | 后缀 | 功能 | 示例 |
|------|------|------|------|
| **chat** | (无) | 标准对话 | `qwen3.7-plus` |
| **thinking** | `-thinking` | 思考模式（CoT） | `qwen3.7-plus-thinking` |
| **search** | `-search` | 联网搜索 | `qwen3.7-plus-search` |
| **deep_research** | `-deep-research` | 深度研究 | `qwen3.7-plus-deep-research` |
| **image** | `-image` | 图片生成 | `qwen3.7-plus-image` |
| **video** | `-video` | 视频生成 | `qwen3.7-plus-video` |
| **webdev** | `-webdev` | 网页开发 | `qwen3.7-plus-webdev` |
| **slides** | `-slides` | 幻灯片生成 | `qwen3.7-plus-slides` |

---

## 🎨 完整模型列表（按系列）

### Qwen3.7 系列（16个）

**Plus 变体（8个）**:
- qwen3.7-plus
- qwen3.7-plus-thinking
- qwen3.7-plus-search
- qwen3.7-plus-deep-research
- qwen3.7-plus-image
- qwen3.7-plus-video
- qwen3.7-plus-webdev
- qwen3.7-plus-slides

**Max 变体（8个）**:
- qwen3.7-max
- qwen3.7-max-thinking
- qwen3.7-max-search
- qwen3.7-max-deep-research
- qwen3.7-max-image
- qwen3.7-max-video
- qwen3.7-max-webdev
- qwen3.7-max-slides

### Qwen3.6 系列（34个）

**Plus（8个）**:
- qwen3.6-plus + 7种模式变体

**Max Preview（6个）**:
- qwen3.6-max-preview + 5种模式变体

**27B（8个）**:
- qwen3.6-27b + 7种模式变体

**35B-A3B（8个）**:
- qwen3.6-35b-a3b + 7种模式变体

**Plus Preview（4个）**:
- qwen3.6-plus-preview + 3种模式变体

### Qwen3.5 系列（58个）

**Plus（8个）**: qwen3.5-plus + 7种模式
**Flash（8个）**: qwen3.5-flash + 7种模式
**Omni-Plus（3个）**: qwen3.5-omni-plus + 2种模式
**Omni-Flash（3个）**: qwen3.5-omni-flash + 2种模式
**27B（8个）**: qwen3.5-27b + 7种模式
**35B-A3B（8个）**: qwen3.5-35b-a3b + 7种模式
**122B-A10B（8个）**: qwen3.5-122b-a10b + 7种模式
**397B-A17B（8个）**: qwen3.5-397b-a17b + 7种模式
**Max Preview（4个）**: qwen3.5-max-2026-03-08 + 3种模式

### Qwen3 系列（30个）

**Max（8个）**: qwen3-max-2026-01-23 + 7种模式
**Coder（7个）**: qwen3-coder-plus + 6种模式
**VL（8个）**: qwen3-vl-plus + 7种模式
**Omni Flash（7个）**: qwen3-omni-flash-2025-12-01 + 6种模式

### 经典系列（18个）

**Qwen Plus 2507（8个）**: qwen-plus-2025-07-28 + 7种模式
**Beta v24（5个）**: qwen-latest-series-invite-beta-v24 + 4种模式
**Beta v16（5个）**: qwen-latest-series-invite-beta-v16 + 4种模式

---

## 💡 能力矩阵

| 模型系列 | Audio | Vision | Search | Thinking | Image Gen | Video Gen | Web Dev | Slides |
|----------|-------|--------|--------|----------|-----------|-----------|---------|--------|
| Qwen3.7-Plus | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Qwen3.7-Max | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Qwen3.6-Plus | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Qwen3.5-Plus | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Qwen3.5-Flash | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Qwen3.5-Omni | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Qwen3-Max | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Qwen3-Coder | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Qwen3-VL | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 🚀 快速使用

### 查询所有模型
```bash
curl http://localhost:7862/v1/models \
  -H "Authorization: Bearer sk-qwen-local-2026"
```

### 使用特定模型
```bash
# 使用最新旗舰模型
curl -X POST http://localhost:7862/v1/chat/completions \
  -H "Authorization: Bearer sk-qwen-local-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.7-max",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 使用思考模式
curl -X POST http://localhost:7862/v1/chat/completions \
  -H "Authorization: Bearer sk-qwen-local-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.7-plus-thinking",
    "messages": [{"role": "user", "content": "解决这个复杂问题..."}]
  }'

# 使用搜索模式
curl -X POST http://localhost:7862/v1/chat/completions \
  -H "Authorization: Bearer sk-qwen-local-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.7-plus-search",
    "messages": [{"role": "user", "content": "最新的AI新闻"}]
  }'
```

---

## 📝 模型选择建议

| 使用场景 | 推荐模型 | 说明 |
|----------|----------|------|
| **通用对话** | qwen3.7-plus | 最新，功能全面 |
| **最强性能** | qwen3.7-max | 旗舰模型 |
| **快速响应** | qwen3.5-flash | 速度优先 |
| **代码任务** | qwen3-coder-plus | 代码专用 |
| **视觉任务** | qwen3-vl-plus | 视觉语言模型 |
| **全模态** | qwen3.5-omni-plus | 音频+视频+图像 |
| **复杂推理** | qwen3.7-plus-thinking | 思考模式 |
| **联网搜索** | qwen3.7-plus-search | 实时信息 |
| **深度研究** | qwen3.7-plus-deep-research | 研究分析 |
| **本地部署** | qwen3.6-27b | 针对本地优化 |

---

## 🔄 更新日志

- **2026-06**: Qwen3.7 系列发布（Plus/Max）
- **2026-03**: Qwen3.6-Max-Preview 发布
- **2026-01**: Qwen3-Max 正式版发布
- **2025-12**: Qwen3-Omni-Flash 发布
- **2025-07**: Qwen3-235B-A22B-2507 发布

---

**项目**: qwen2API
**更新**: 2026-06-12
**来源**: `/v1/models` API
