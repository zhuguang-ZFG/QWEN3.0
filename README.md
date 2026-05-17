# red V1-Flash

> 深圳市动力巢科技 (www.donglicao.com)
> 基于 Qwen3-8B + QLoRA 微调的 CNC/嵌入式/逆向工程 领域专精大模型

---

## 架构

```
用户输入 → Router V3 (语义路由+意图识别+质量评分)
  ├─ CNC/ESP32/SVG → red V1-Flash 本地 (免费)
  ├─ 复杂推理 → LongCat Thinking + red V1-Flash
  ├─ 质量兜底 → Claude API (right.codes)
  └─ 超长上下文 → DeepSeek 1M API
         ↑
    rtk Token 压缩 (省 60-90% API 费用)
```

## 核心能力

| 领域 | 覆盖 |
|------|------|
| CNC/Grbl | GCode、步进控制、归零、限位、参数调优 |
| ESP32/STM32 | GPIO/I2C/SPI/UART、固件开发、FreeRTOS |
| SVG/图像 | 矢量处理、Inkscape插件、SVG→GCode |
| 逆向工程 | 固件提取、JTAG/SWD、协议分析、Ghidra |
| AI 工具链 | Claude Code/Cursor/CC-switch 优化 |

## 训练管线

| 轮次 | 基座 | 数据量 | 方法 | 状态 |
|------|------|--------|------|------|
| R1 | Qwen2.5-7B | 98K | SFT QLoRA | ✅ |
| R2 | Qwen2.5-7B | 206K | SFT QLoRA | ✅ |
| R3 | Qwen2.5-7B | 208K | SFT QLoRA | ✅ |
| R4 | Qwen3-8B | 208K | SFT QLoRA (4096 ctx) | 🔄 |
| R5 | Qwen3-8B | 100K | SFT QLoRA + DPO | ⏳ |
| DPO | Qwen3-8B | 500+ 偏好对 | DPO QLoRA | ⏳ |

## 路由系统

| 版本 | 核心功能 |
|------|----------|
| V1 | 关键词路由 + 本地/API + 断网兜底 |
| V2 | RAG + 质量评分 + 缓存 + 流式 + 推理引擎 |
| V3 | 语义路由 + 意图识别 + 多模型共识 + 断路器 + 会话持久化 |

## API 供应商 (7 个)

| 供应商 | 类型 | 成本 |
|------|------|------|
| red V1-Flash (LM Studio) | 本地 | 免费 |
| Claude Sonnet 4.6 (right.codes) | 付费 | 低 |
| DeepSeek V4 (官方) | 付费 | 极低 |
| GPT 5.5 (right.codes) | 付费 | 低 |
| DeepSeek V4 Flash (Nvidia) | 免费 | 免费 |
| DeepSeek V4 Flash (OpenRouter) | 免费 | 免费 |
| Nemotron 120B (OpenRouter) | 免费 | 免费 |

## 关键优化

| 优化 | 来源 | 效果 |
|------|------|------|
| 极致简洁响应 | Claude Code 2.0 内部提示词 | 减少废话 |
| KNOW WHEN TO STOP | Orchids.app 提示词 | 不画蛇添足 |
| RAG 代码检索 | 自定义 RAG 索引 | 基于原文回答 |
| 三路蒸馏 | Claude + DeepSeek + GPT | 1695 高质量问答 |
| Abliteration 去审查 | Dolphin + better-uncensored | 移除拒绝向量 |
| 知识边界训练 | HypoTermInstruct 模式 | 主动说"不知道" |
| rtk Token 压缩 | rtk v0.40 | API 费用降低 60-90% |
| CC-switch 集成 | 自定义预设 | Claude Code/Cursor 中直接切换 |

## 反幻觉措施

- ✅❓❌ 确定性标注系统
- RAG 基于原文回答
- 多模型共识验证
- 质量评分 + API 兜底
- "我不知道" 训练数据
- 断路器防雪崩

## 快速开始

```bash
# 启动本地推理
lms server start
lms load qwen3-8b

# 启动路由系统
python router_v3.py

# 启动 Web UI
python web_chat.py

# 健康检测
python api_health_checker.py

# 自动发现新免费 API
python api_auto_discovery.py
```
