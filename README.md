# red V1flash - CNC/嵌入式领域 AI 助手

基于 Qwen3-8B + QLoRA 微调的 CNC/嵌入式领域专精 AI 助手服务，通过智能路由将用户问题分发到最合适的后端，对外统一呈现为 **red V1flash**。

详细架构设计请参阅 [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 核心架构

```
用户输入
    │
    ▼
┌─────────────────────────────────────┐
│         两层意图分类                 │
│  Layer 1: 关键词规则 (80% 命中)      │
│  Layer 2: 本地模型 (20% 模糊查询)    │
└──────────────┬──────────────────────┘
               │ intent + complexity
               ▼
┌─────────────────────────────────────┐
│         Prompt 扩写                  │
│  本地模型将短问题扩写为技术详细问题   │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
  本地模型          外部 API
  (GRBL/GCode)   ┌──────────────┐
                 │ Claude       │ ← 复杂故障/架构设计
                 │ LongCat系列  │ ← 嵌入式/代码/通用
                 └──────────────┘
               │
               ▼
    响应清洗（隐藏底层模型名）
               │
               ▼
        red V1flash 统一输出
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install python-dotenv
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入真实 API Key
```

### 3. 启动本地推理（可选，用于 GRBL/GCode 本地回答）

```bash
# 使用 LM Studio 加载本地模型，默认监听 http://localhost:1234
lms server start
lms load qwen3-8b
```

### 4. 运行智能路由器

```bash
# 交互式 CLI
python smart_router.py

# MCP 服务模式（供 Claude Code 调用）
python smart_router.py --mcp

# 调试模式（显示路由详情和 Prompt 扩写）
RED_DEBUG=1 python smart_router.py
```

---

## 意图路由表

| 意图 (intent) | 触发关键词示例 | 后端 | 说明 |
|---|---|---|---|
| `grbl_config` | `$100`、`步数/mm`、`归零`、`$22` | 本地模型 | GRBL 参数训练数据充足，本地直答 |
| `gcode_help` | `G0`、`G2`、`M3`、`圆弧`、`插补` | 本地模型 | G 代码解释，本地直答 |
| `cnc_trouble` | `失步`、`抖动`、`限位`、`报警` | Claude | 复杂故障诊断，调用最强模型 |
| `embedded_dev` | `ESP32`、`STM32`、`FreeRTOS`、`DMA` | LongCat Thinking | 嵌入式开发，需要推理能力 |
| `code_generation` | `写代码`、`生成代码`、`实现函数` | LongCat Chat | 代码生成，快速响应 |
| `architecture` | `架构`、`方案`、`选型`、`对比` | Claude | 架构设计，调用最强模型 |
| `complex_theory` | `FOC`、`PID`、`闭环`、`伺服` | LongCat Thinking | 复杂理论，需要推理能力 |
| `general_cnc` | `PCB`、`激光`、`主轴`、`RPM` | LongCat Lite | 通用 CNC，最快响应 |
| `unknown` | 其他 | LongCat Chat | 兜底后端 |

---

## 训练数据说明

共 **156,414 条** CNC/嵌入式领域问答对，来源分布：

| 数据来源 | 说明 |
|---|---|
| StackExchange | CNC/嵌入式相关技术问答 |
| 知乎 | 中文 CNC/嵌入式讨论 |
| GRBL 源码蒸馏 | 从 GRBL 源码提取参数、错误码、报警码知识 |
| 本地代码蒸馏 | 从本地项目代码提取实现细节 |
| Claude 专家问答 | 三路蒸馏（Claude + DeepSeek + GPT）生成高质量问答 |

---

## 模型训练

### 训练配置

- 基座模型：Qwen3-8B
- 训练方式：QLoRA（rank=16，alpha=32，4-bit 量化）
- 序列长度：4096 tokens
- 硬件要求：RTX 5060 Ti 16GB（或同等 VRAM）
- 有效批次大小：8（batch=1 × gradient_accumulation=8）

### 运行训练

```bash
# 设置训练数据路径（默认读取 round5_training_data.json）
export TRAIN_DATA_PATH=/path/to/your/training_data.json

# 开始训练
python train_model.py

# 仅导出 GGUF（跳过训练）
python train_model.py --export_only

# 通过 llama.cpp 导出
python train_model.py --export_only --use_llama_cpp
```

### 训练轮次记录

| 轮次 | 基座 | 数据量 | 方法 | 状态 |
|---|---|---|---|---|
| R1-R3 | Qwen2.5-7B | 98K-208K | SFT QLoRA | 已完成 |
| R4-R7 | Qwen3-8B | 156K+ | SFT QLoRA | 进行中（R7 step 1000/4000，loss=1.05）|

---

## MCP 集成（Claude Code）

smart_router.py 内置 MCP stdio 服务，可作为 Claude Code 工具使用。

### 配置方法

在 Claude Code 的 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "red-v1-flash": {
      "command": "python",
      "args": ["/path/to/QWEN3.0/smart_router.py", "--mcp"],
      "env": {
        "CLAUDE_API_KEY": "your_key",
        "LONGCAT_API_KEY": "your_key"
      }
    }
  }
}
```

### 可用 MCP 工具

| 工具名 | 功能 |
|---|---|
| `cnc_route` | 分析 CNC/嵌入式问题，自动路由到最佳后端 |
| `grbl_lookup` | 查询 GRBL 参数（`$0`-`$132`）、错误码、报警码、G 代码 |

---

## 目录结构

| 文件 | 用途 |
|---|---|
| `smart_router.py` | 智能路由器核心（两层路由 + Prompt 扩写 + MCP 服务） |
| `train_model.py` | QLoRA 训练脚本（Qwen3-8B，RTX 5060 Ti 适配） |
| `closed_loop.py` | 闭环训练流程（自动评估 → 触发重训） |
| `grpo_train.py` | GRPO 强化学习训练 |
| `lora_merge.py` | LoRA 权重合并导出 |
| `evaluate_model.py` | 模型评估脚本 |
| `extract_grbl_qa.py` | GRBL 知识问答生成 |
| `extract_grbl_training.py` | GRBL 源码蒸馏 |
| `distill_local_code.py` | 本地代码蒸馏 |
| `collect_zhihu_data.py` | 知乎数据采集 |
| `append_datasets.py` | 多数据集合并 |
| `web_chat.py` | Web 聊天界面 |
| `router_v3.py` | 旧版路由器（已由 smart_router.py 取代） |
| `.env.example` | 环境变量模板 |

---

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `CLAUDE_API_KEY` | Claude API Key（right.codes） | 必填 |
| `LONGCAT_API_KEY` | LongCat API Key | 必填 |
| `PUBLIC_MODEL_NAME` | 对外展示的模型名 | `red V1flash` |
| `RED_DEBUG` | 调试模式（显示路由详情） | `0` |

---

> 深圳市动力巢科技 (www.donglicao.com)
