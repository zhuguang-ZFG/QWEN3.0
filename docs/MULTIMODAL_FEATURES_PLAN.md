# LiMa AI 多模态功能扩展方案

> 版本: 1.0 | 日期: 2026-05-19
> 原则: 不降级，零成本优先，复用现有 20+ 免费后端

---

## 一、功能概览

| 功能 | 触发方式 | 后端 | 成本 | 优先级 |
|------|----------|------|------|--------|
| 深度思考 | 用户开关 / 自动检测 | DeepSeek R1 | 免费 | P0 |
| AI 生图 | "画一个..." / 图片按钮 | SiliconFlow / Pollinations | 免费 | P1 |
| 拍题答疑 | 上传图片 / 拍照 | Qwen-VL / DeepSeek-VL | 免费 | P1 |

---

## 二、深度思考模式

### 2.1 用户体验

```
用户输入: "帮我分析一下这段代码的性能瓶颈"
                    ↓
路由检测: 复杂分析类 → 启用 thinking
                    ↓
前端展示: [思考中...] → 折叠的思考过程 → 最终答案
```

### 2.2 技术实现

**路由层改动 (smart_router.py):**
- 新增意图标签: `thinking_required`
- 触发条件: 用户手动开启 OR 检测到复杂推理/分析/数学证明
- 后端选择: DeepSeek R1 (免费, 支持 thinking tokens)

**API 协议扩展:**
```json
{
  "model": "lima-1.3",
  "messages": [...],
  "thinking": true,
  "thinking_budget": 8000
}
```

**响应格式 (兼容 OpenAI):**
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "最终答案...",
      "thinking": "思考过程（可折叠展示）..."
    }
  }]
}
```

### 2.3 可用免费后端

| 后端 | Thinking 支持 | 延迟 | 质量 |
|------|--------------|------|------|
| DeepSeek R1 | 原生支持 | 3-8s | 极高 |
| Qwen3 (thinking mode) | 原生支持 | 2-5s | 高 |
| Longcat Thinking | 支持 | 2-4s | 高 |

### 2.4 前端改动 (NextChat)

通过 nginx sub_filter 注入 JS:
- 添加"深度思考"开关按钮
- 检测响应中的 thinking 字段
- 折叠展示思考过程（点击展开）

### 2.5 GitHub 参考

- [deepseek-ai/DeepSeek-R1](https://github.com/deepseek-ai/DeepSeek-R1)
- [open-webui](https://github.com/open-webui/open-webui) — 已支持 thinking 展示

---

## 三、AI 生图模式

### 3.1 用户体验

```
用户输入: "画一只在月球上弹吉他的猫"
                    ↓
路由检测: 生图意图 → 走图片生成通道
                    ↓
前端展示: [生成中...] → 图片卡片 + 下载按钮
```

### 3.2 技术实现

**意图检测规则 (smart_router.py):**
```python
IMAGE_TRIGGERS = [
    r"画[一个]?", r"生成.*图", r"画.*图",
    r"设计.*logo", r"创作.*插画",
    r"generate.*image", r"draw.*",
    r"create.*picture", r"make.*illustration"
]
```

**API 协议 (兼容 OpenAI Images API):**
```json
// 请求
POST /v1/images/generations
{
  "prompt": "一只在月球上弹吉他的猫",
  "model": "lima-image",
  "size": "1024x1024",
  "n": 1
}

// 响应
{
  "data": [{"url": "https://...png", "revised_prompt": "..."}]
}
```

**路由策略:**
- 检测到生图意图 → 不走 chat 通道，转发到 images API
- 在 chat 响应中嵌入图片 markdown: `![image](url)`

### 3.3 可用免费后端

| 后端 | 模型 | 限制 | 质量 |
|------|------|------|------|
| Pollinations.ai | FLUX / SD3 | 无限免费 | 高 |
| SiliconFlow | FLUX-schnell | 免费额度 | 高 |
| Together.ai | FLUX-1.1-pro | 免费额度 | 极高 |
| Cloudflare Workers AI | SD-XL | 免费 10K/天 | 中 |

### 3.4 前端改动

- 检测 AI 回复中的图片 URL → 渲染为图片卡片
- 添加"生图模式"按钮（可选，也可自动检测）
- 图片支持：放大查看、下载、重新生成

### 3.5 GitHub 参考

- [pollinations/pollinations](https://github.com/pollinations/pollinations) — 免费生图 API
- [siliconflow/siliconflow](https://siliconflow.cn) — 国内免费 FLUX
- [lobehub/lobe-chat](https://github.com/lobehub/lobe-chat) — 已集成生图展示

---

## 四、拍题答疑模式 (Vision)

### 4.1 用户体验

```
用户操作: 拍照/上传数学题图片
                    ↓
前端处理: 图片压缩 → base64 编码 → 发送
                    ↓
路由检测: 消息含图片 → 走 Vision 后端
                    ↓
AI 响应: OCR识别题目 → 分步解答 → 展示答案
```

### 4.2 技术实现

**消息格式 (OpenAI Vision 兼容):**
```json
{
  "model": "lima-1.3",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "请解答这道题"},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]
  }]
}
```

**路由策略:**
```python
def detect_vision_request(messages):
    """检测消息中是否包含图片"""
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "image_url":
                    return True
    return False
```

**系统提示词注入 (拍题场景):**
```
你是一位耐心的老师。用户上传了一道题目的图片。
请：1. 识别题目内容 2. 分步骤解答 3. 给出最终答案
如果是选择题，明确指出正确选项。
```

### 4.3 可用免费 Vision 后端

| 后端 | 模型 | 图片支持 | 质量 |
|------|------|----------|------|
| DeepSeek | DeepSeek-VL2 | 多图 | 高 |
| Qwen | Qwen-VL-Max | 多图 | 极高 |
| Longcat | longcat-omni | 单图 | 高 |
| SiliconFlow | InternVL2 | 多图 | 高 |

### 4.4 前端改动

- 添加📷拍照按钮 + 📎上传按钮
- 图片预览（缩略图）
- 图片压缩（限制 1MB 以内，提升速度）
- 移动端适配（调用系统相机）

### 4.5 与写字机联动

```
拍题 → AI解答 → 用户确认 → 写字机手写答案到纸上
```

这是动力巢独有的差异化能力：AI + 硬件闭环。

### 4.6 GitHub 参考

- [QwenLM/Qwen-VL](https://github.com/QwenLM/Qwen-VL) — 开源 Vision 模型
- [deepseek-ai/DeepSeek-VL2](https://github.com/deepseek-ai/DeepSeek-VL2)
- [lobehub/lobe-chat](https://github.com/lobehub/lobe-chat) — 已支持图片上传

---

## 五、实施路线图

### Sprint 1 (1周): 深度思考

| 步骤 | 工作量 | 内容 |
|------|--------|------|
| 1 | 2h | smart_router.py 添加 thinking 意图检测 |
| 2 | 2h | 路由到 DeepSeek R1 / Qwen3 thinking |
| 3 | 4h | 前端注入 thinking 展示 CSS/JS |
| 4 | 2h | 测试 + 部署 |

### Sprint 2 (1周): AI 生图

| 步骤 | 工作量 | 内容 |
|------|--------|------|
| 1 | 2h | 添加 Pollinations/SiliconFlow 后端 |
| 2 | 3h | 生图意图检测 + /v1/images 路由 |
| 3 | 3h | 前端图片渲染组件 |
| 4 | 2h | 测试 + 部署 |

### Sprint 3 (1周): 拍题答疑

| 步骤 | 工作量 | 内容 |
|------|--------|------|
| 1 | 2h | Vision 消息检测 + 路由 |
| 2 | 2h | 接入 Qwen-VL / DeepSeek-VL |
| 3 | 4h | 前端拍照/上传组件 |
| 4 | 2h | 移动端适配 + 测试 |

---

## 六、架构变更总览

```
                    ┌─────────────────────────┐
                    │   用户输入              │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │   意图分类器            │
                    │   (扩展 3 个新意图)      │
                    └───┬───────┬─────────┬───┘
                        │       │         │
            ┌───────────▼──┐ ┌──▼────┐ ┌──▼──────────┐
            │ thinking     │ │ image │ │ vision      │
            │ DeepSeek R1  │ │ FLUX  │ │ Qwen-VL     │
            │ Qwen3-think  │ │ SD3   │ │ DeepSeek-VL │
            └──────────────┘ └───────┘ └─────────────┘
                        │       │         │
                    ┌───▼───────▼─────────▼───┐
                    │   统一响应格式化         │
                    │   (thinking折叠/图片卡片) │
                    └─────────────────────────┘
```

---

## 七、成本分析

| 功能 | 日均请求(预估) | 单次成本 | 月成本 |
|------|---------------|----------|--------|
| 深度思考 | 100次 | ¥0 | ¥0 |
| AI 生图 | 50次 | ¥0 | ¥0 |
| 拍题答疑 | 200次 | ¥0 | ¥0 |
| **总计** | **350次** | - | **¥0** |

全部使用免费后端，商业化初期零成本运营。

---

## 八、竞品对比

| 能力 | LiMa AI | ChatGPT | DeepSeek | Kimi |
|------|---------|---------|----------|------|
| 深度思考 | ✅ 免费 | ✅ 付费 | ✅ 免费 | ❌ |
| AI 生图 | ✅ 免费 | ✅ 付费 | ❌ | ❌ |
| 拍题答疑 | ✅ 免费 | ✅ 付费 | ❌ | ✅ 免费 |
| 硬件联动 | ✅ 独有 | ❌ | ❌ | ❌ |
| 编程辅助 | ✅ 免费 | ✅ 付费 | ✅ 免费 | ❌ |
| 智能路由 | ✅ 20+后端 | ❌ 单模型 | ❌ 单模型 | ❌ |

**核心差异化: AI + 硬件闭环（写字机/绘图机/激光雕刻机）**
