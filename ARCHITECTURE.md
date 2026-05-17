# red V1flash 系统架构文档

**最后更新：** 2026-05-18
**维护方：** 深圳市动力巢科技 (www.donglicao.com)

---

## 1. 项目定位

red V1flash 是面向 CNC/嵌入式领域的 AI 助手服务，通过智能路由将用户问题分发到最合适的后端模型，对外统一呈现为单一品牌名。它不是自研大模型，而是"蒸馏 + 微调 + 路由"三层架构的领域专精服务，核心价值在于低成本获得接近顶级模型的 CNC/嵌入式领域回答质量。

---

## 2. 整体架构图

```
用户输入
    │
    ▼
┌──────────────────────────────────────────────┐
│              两层意图分类                      │
│  Layer 1: 关键词规则 (80% 命中, ~0ms)         │
│  Layer 2: 本地模型意图分析 (20% 模糊, 2-5s)   │
└──────────────────┬───────────────────────────┘
                   │ intent + complexity
                   ▼
┌──────────────────────────────────────────────┐
│              Prompt 扩写                       │
│  本地模型将短问题扩写为技术详细问题 (<300字)   │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│           降级链路由 (FALLBACK_CHAINS)         │
│  主力后端 → 备用1 → 备用2 → 最终兜底           │
│  熔断器保护：连续失败3次触发，60秒恢复          │
└──┬───────┬──────┬──────┬──────┬──────────────┘
   │       │      │      │      │
   ▼       ▼      ▼      ▼      ▼
 本地    Claude  DeepSeek Nvidia LongCat
 模型    (架构)  (故障)   NIM    (代码/通用)
   │       │      │      │      │
   └───────┴──────┴──────┴──────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│              质量保障层                        │
│  GRBL参数验证 │ 截断检测续写 │ 不确定性升级    │
│  免责声明清洗 │ 模型名隐藏                     │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
           red V1flash 统一输出
                   │
    ┌──────────────┘
    ▼
┌──────────────────────────────────────────────┐
│         自动蒸馏 + 持续训练系统（设计中）       │
│  低质量回答 → 蒸馏队列 → 质量门控 → 增量训练   │
└──────────────────────────────────────────────┘
```

---

## 3. 智能路由器（smart_router.py）

### 3.1 两层意图分类

**Layer 1：关键词规则层（~0ms，命中率约 80%）**

触发条件：正则匹配置信度 >= 0.80 时直接返回，跳过 Layer 2。

| 序号 | 正则模式 | 意图 | 置信度 |
|------|---------|------|--------|
| 1 | `\$\d+`、`步数.*mm`、`steps_per_mm` | grbl_config | 0.95 |
| 2 | `归零`、`homing`、`$22-$27` | grbl_config | 0.95 |
| 3 | `G0/G1/G2/G3/G28/G38/G54/G92`、`M3/M5/M8`、`圆弧`、`插补` | gcode_help | 0.90 |
| 4 | `error:\d+`、`alarm:\d+`、`ALARM`、`报警`、`错误码` | grbl_config | 0.90 |
| 5 | `失步`、`抖动`、`噪音`、`异响`、`卡顿`、`不动`、`乱走`、`偏移` | cnc_trouble | 0.85 |
| 6 | `限位`、`limit switch`、`触发`、`短路`、`接线` | cnc_trouble | 0.85 |
| 7 | `ESP32`、`WiFi`、`蓝牙`、`WebUI`、`OTA`、`FreeRTOS`、`RTOS` | embedded_dev | 0.85 |
| 8 | `STM32`、`HAL`、`CubeMX`、`定时器`、`中断`、`DMA`、`寄存器` | embedded_dev | 0.85 |
| 9 | `写.*代码`、`生成.*代码`、`实现.*函数`、`代码示例` | code_generation | 0.85 |
| 10 | `FOC`、`PID`、`闭环`、`编码器`、`伺服`、`变频器`、`VFD` | complex_theory | 0.85 |
| 11 | `架构`、`设计`、`方案`、`选型`、`对比`、`哪个好` | architecture | 0.80 |
| 12 | `PCB`、`雕刻`、`激光`、`切割`、`主轴`、`转速`、`RPM` | general_cnc | 0.80 |

**Layer 2：本地模型意图分析（2-5s，处理约 20% 模糊查询）**

触发条件：Layer 1 未命中（置信度 < 0.80）时调用本地 LM Studio 模型。

输出 JSON 字段：`intent`、`complexity (0-1)`、`needs_code`、`domain_keywords`、`cnc_subdomain`。

### 3.2 后端清单（18个）

| 后端名 | 模型 | 用途 | 费用 | API格式 |
|--------|------|------|------|---------|
| claude | claude-sonnet-4-6 | 架构设计、复杂综合 | 付费 | Anthropic |
| longcat_lite | LongCat-Flash-Lite | 通用CNC快速响应 | 付费 | Anthropic |
| longcat_chat | LongCat-Flash-Chat | 代码/通用兜底 | 付费 | Anthropic |
| longcat_thinking | LongCat-Flash-Thinking-2601 | 嵌入式推理 | 付费 | Anthropic |
| longcat_omni | LongCat-Flash-Omni-2603 | 多模态（无system字段） | 付费 | Anthropic |
| longcat | LongCat-2.0-Preview | 最终兜底 | 付费 | Anthropic |
| deepseek_pro | deepseek-v4-pro | CNC故障诊断（强推理） | 付费 | Anthropic |
| deepseek_pro_1m | deepseek-v4-pro | 超长上下文分析 | 付费 | Anthropic |
| deepseek_flash | deepseek-v4-flash | 代码生成备用 | 付费 | Anthropic |
| deepseek_flash_1m | deepseek-v4-flash | 超长上下文快速 | 付费 | Anthropic |
| nvidia_nemotron | nvidia/llama-3.3-nemotron-super-49b-v1 | 嵌入式/复杂理论 | 免费额度 | OpenAI |
| nvidia_llama70b | meta/llama-3.3-70b-instruct | 未知意图兜底 | 免费额度 | OpenAI |
| nvidia_qwen_coder | qwen/qwen3-coder-480b-a35b-instruct | 代码生成主力 | 免费额度 | OpenAI |
| nvidia_llama4 | meta/llama-4-maverick-17b-128e-instruct | 通用CNC主力 | 免费额度 | OpenAI |
| nvidia_mistral | mistralai/mistral-large-3-675b-instruct-2512 | 备用 | 免费额度 | OpenAI |
| nvidia_phi4 | microsoft/phi-4-mini-instruct | 轻量备用 | 免费额度 | OpenAI |
| chinamobile | minimax-m25 | 通用兜底（国内） | 付费 | OpenAI |
| local | local-model (LM Studio) | GRBL/GCode本地直答 | 免费 | OpenAI |

### 3.3 路由策略（ROUTE + FALLBACK_CHAINS）

| 意图 | 主力后端 | 降级链（按顺序） |
|------|---------|----------------|
| cnc_trouble | deepseek_pro | deepseek_pro → nvidia_nemotron → claude → longcat |
| grbl_config | local | local → nvidia_llama4 → longcat_lite |
| gcode_help | local | local → nvidia_llama4 → longcat_lite |
| embedded_dev | nvidia_nemotron | nvidia_nemotron → deepseek_pro → claude → longcat_thinking |
| code_generation | nvidia_qwen_coder | nvidia_qwen_coder → deepseek_flash → nvidia_llama70b → longcat_chat |
| architecture | claude | claude → deepseek_pro → nvidia_nemotron → longcat |
| general_cnc | nvidia_llama4 | nvidia_llama4 → longcat_lite → nvidia_llama70b → chinamobile |
| complex_theory | nvidia_nemotron | nvidia_nemotron → deepseek_pro → claude → longcat_thinking |
| unknown | nvidia_llama70b | nvidia_llama70b → longcat_chat → nvidia_llama4 → chinamobile → longcat |

降级链过滤规则：无 API Key 的后端自动跳过（`local` 除外）。

### 3.4 质量保障层

**GRBL 参数验证范围表**

| 参数 | 合理范围 | 说明 |
|------|---------|------|
| $0 | 1 - 255 | 步进脉冲时间(μs) |
| $1 | 0 - 255 | 步进空闲延迟(ms) |
| $2 | 0 - 7 | 步进端口反转掩码 |
| $3 | 0 - 7 | 方向端口反转掩码 |
| $4 | 0 - 1 | 步进使能反转 |
| $11 | 0.0 - 10.0 | 结点偏差(mm) |
| $12 | 0.0 - 1.0 | 圆弧容差(mm) |
| $24 | 1.0 - 10000.0 | 归零进给速率(mm/min) |
| $25 | 1.0 - 100000.0 | 归零搜索速率(mm/min) |
| $27 | 0.0 - 100.0 | 归零回退距离(mm) |
| $100-$102 | 1.0 - 10000.0 | X/Y/Z 步数/mm |
| $110-$112 | 1.0 - 100000.0 | X/Y/Z 最大速率(mm/min) |
| $120-$122 | 1.0 - 100000.0 | X/Y/Z 加速度(mm/s²) |
| $130-$132 | 0.0 - 100000.0 | X/Y/Z 最大行程(mm) |

超出范围时在回答末尾追加警告：`⚠️ 参数提示：$xxx=yyy 超出合理范围 [lo, hi]，请结合实际硬件验证。`

**截断检测逻辑**

满足以下任一条件判定为截断：
- 文本长度 < 20 字符
- 代码块 ` ``` ` 数量为奇数（未闭合）
- 文本长度 > 100 且末尾字符为字母/数字（非句号/问号/括号等）

截断后自动续写：向同一后端发送 `请继续完成上面的回答。`，追加到原回答末尾。

**不确定性升级条件**

检测到以下信号词时，自动升级到 `deepseek_pro` 重新回答：
`我不确定`、`可能是`、`大概`、`也许`、`不太清楚`、`不确定`、`需要更多信息`、`取决于具体情况`、`not sure`、`might be`、`possibly`、`uncertain`

升级条件：当前后端不是 `claude` 或 `deepseek_pro`，且升级后回答不含不确定性信号。

**免责声明清洗**

自动删除以下模式的句子：`作为AI...`、`我无法保证...`、`建议咨询专业...`、`请注意...安全...`、`以上仅供参考...`、`作为...语言模型...`

### 3.5 熔断器参数

| 参数 | 值 | 说明 |
|------|-----|------|
| CB_FAILURE_THRESHOLD | 3 | 连续失败次数触发熔断 |
| CB_RECOVERY_TIMEOUT | 60秒 | 熔断后等待时间（open 状态） |
| CB_SUCCESS_THRESHOLD | 2 | half-open 状态下连续成功次数才关闭熔断 |

**状态转换：**

```
closed ──(连续失败≥3次)──> open
open   ──(超过60秒)──────> half-open
half-open ──(成功≥2次)──> closed
half-open ──(失败≥3次)──> open
```

熔断中的后端返回 `None`，路由器自动跳到降级链下一个后端。

### 3.6 模型名隐藏机制

`PUBLIC_MODEL_NAME` 默认值为 `red V1flash`，可通过环境变量覆盖。

`CLEAN_PATTERNS` 清洗规则（正则替换为 `PUBLIC_MODEL_NAME` 或空字符串）：

| 匹配模式 | 替换为 |
|---------|--------|
| `claude[\w\-\.]*` | red V1flash |
| `longcat[\w\-\.]*` | red V1flash |
| `deepseek[\w\-\.\[\]]*` | red V1flash |
| `gpt-?4[\w\-\.]*` | red V1flash |
| `nvidia[\w\-\.\/]*` | red V1flash |
| `nemotron[\w\-\.]*` | red V1flash |
| `llama[\w\-\.]*` | red V1flash |
| `mistral[\w\-\.]*` | red V1flash |
| `qwen[\w\-\.]*` | red V1flash |
| `phi[\w\-\.]*` | red V1flash |
| `minimax[\w\-\.]*` | red V1flash |
| `anthropic` | （删除） |
| `openai` | （删除） |

清洗在两处执行：`call_api()` 返回时 + `route()` 最终输出时（双重保障）。

### 3.7 MCP 集成

smart_router.py 内置 MCP stdio 服务，协议版本 `2024-11-05`。

**Claude Code 配置示例（~/.claude/mcp_servers.json）：**

```json
{
  "mcpServers": {
    "red-v1-flash": {
      "command": "python",
      "args": ["D:/GIT/smart_router.py", "--mcp"],
      "env": {
        "CLAUDE_API_KEY": "your_key",
        "LONGCAT_API_KEY": "your_key",
        "NVIDIA_API_KEY": "your_key",
        "DEEPSEEK_API_KEY": "your_key"
      }
    }
  }
}
```

**可用 MCP 工具：**

| 工具名 | 输入参数 | 功能 |
|--------|---------|------|
| `cnc_route` | `query` (必填), `prefer_backend` (可选: claude/longcat/local) | 分析意图，路由到最佳后端，返回 intent/complexity/answer/timing_ms |
| `grbl_lookup` | `item` (如 $100, error:1, G2, M3) | 查询 GRBL 参数/错误码/报警码/G代码，调用本地模型回答 |

---

## 4. 自动蒸馏 + 持续训练系统（设计方案）

### 4.1 系统状态机

```
         ┌─────────────────────────────────────┐
         │                                     │
         ▼                                     │
    [IDLE/监控]                                 │
         │                                     │
    (新回答入队)                                │
         ▼                                     │
  [DISTILL/蒸馏调度]                            │
    distill_scheduler.py                       │
         │                                     │
    (批量蒸馏完成)                              │
         ▼                                     │
  [QUALITY_GATE/质量门控]                       │
    quality_gate.py                            │
         │                    │                │
    (通过≥80%)           (不通过)               │
         ▼                    ▼                │
  [TRAIN/增量训练]      [DISCARD/丢弃]          │
    auto_trainer.py                            │
         │                                     │
    (训练完成)                                  │
         ▼                                     │
  [EVAL/评估循环]                               │
    eval_loop.py                               │
         │                    │                │
    (指标提升)           (指标下降)              │
         ▼                    ▼                │
  [REGISTER/注册]       [ROLLBACK/回滚]         │
    model_registry.py         │                │
         │                    └────────────────┘
         └─────────────────────────────────────┘
```

### 4.2 五个模块详细接口

**quality_gate.py — 质量门控**

职责：对蒸馏生成的 Q&A 对进行多维度质量评分，过滤低质量样本。

```python
# 数据结构
QAPair = {
    "query": str,           # 用户问题
    "answer": str,          # 模型回答
    "intent": str,          # 意图分类（来自 smart_router）
    "source_backend": str,  # 生成回答的后端名
    "teacher_backends": list[str],  # 参与交叉验证的后端列表
    "all_answers": list[str],       # 所有后端的原始回答
}

ScoreDetail = {
    "total": float,          # 综合分 0.0-1.0
    "accuracy": float,       # 技术准确性（GRBL参数范围验证）0.4权重
    "completeness": float,   # 回答完整性（长度/结构）0.25权重
    "consistency": float,    # 多模型一致性（嵌入余弦相似度）0.2权重
    "format": float,         # 格式规范（代码块/单位/步骤）0.15权重
    "passed": bool,          # total >= threshold
    "rejection_reason": str, # 不通过时的原因
}

def score(qa_pair: dict) -> ScoreDetail:
    """对单条 Q&A 对进行质量评分。
    - accuracy: 提取回答中的 GRBL 参数值，与 GRBL_PARAM_RANGES 对比
    - completeness: 长度 100-2000 字符为满分，过短/过长扣分
    - consistency: 计算 all_answers 两两嵌入余弦相似度均值（需 sentence-transformers）
    - format: 检查代码块是否闭合、是否有单位、是否有步骤编号
    """

def filter_batch(pairs: list[dict], threshold: float = 0.75) -> tuple[list[dict], list[dict]]:
    """批量过滤，返回 (passed_list, rejected_list)。"""

def dedup(pair: dict, existing_hashes: set) -> bool:
    """MinHash 去重，返回 True 表示重复（应丢弃）。
    使用 datasketch.MinHash，jaccard 阈值 0.85。
    existing_hashes 从 D:/GIT/data/training_data/ 全量数据预计算。
    """

def sanitize_pii(text: str) -> str:
    """脱敏：替换公司名/文件路径/IP地址/手机号为占位符。"""
```

---

**model_registry.py — 模型版本注册**

职责：记录每个训练轮次的 adapter 路径、评估指标、激活状态，支持回滚。

```python
# 数据结构（持久化到 D:/GIT/data/models/registry.json）
ModelRecord = {
    "version": str,          # 如 "r7_step4000"
    "adapter_path": str,     # 如 "D:/GIT/my_code_model_qwen3/"
    "base_model": str,       # 如 "Qwen3-8B"
    "metrics": {
        "loss": float,
        "grbl_acc": float,   # GRBL 参数题准确率
        "cnc_acc": float,    # CNC 故障题准确率
        "embed_acc": float,  # 嵌入式题准确率
        "overall": float,    # 综合分
    },
    "training_data_count": int,
    "created_at": str,       # ISO8601
    "active": bool,          # 只有一个版本为 True
    "notes": str,
}

def register(adapter_path: str, metrics: dict, notes: str = "") -> ModelRecord:
    """注册新版本，写入 registry.json，不自动激活。"""

def get_active() -> ModelRecord | None:
    """返回当前激活的模型记录，无则返回 None。"""

def promote(version: str) -> bool:
    """激活指定版本（同时停用其他版本），更新 LM Studio 软链接。
    Windows 下使用 junction 而非 symlink（无需管理员权限）。
    """

def rollback() -> ModelRecord | None:
    """回滚到上一个激活版本，返回回滚后的记录。"""

def list_versions() -> list[ModelRecord]:
    """返回所有版本，按 created_at 降序。"""
```

---

**distill_scheduler.py — 蒸馏调度**

职责：GPU 空闲时，从题库取题，并发调用多个强模型生成高质量 Q&A 对，写入待质检目录。

Superpower 原则：按意图匹配最强教师模型——代码题用 Qwen Coder 480B，故障诊断用 DeepSeek PRO，嵌入式用 Nvidia Nemotron，通用用 Claude。

```python
# 数据结构
DistillJob = {
    "job_id": str,           # uuid
    "query": str,
    "intent": str,
    "priority": float,       # 0.0-1.0，越高越优先
    "source": str,           # "user_log" | "variant" | "synthetic"
    "teacher_backends": list[str],  # 3个互补后端
    "status": str,           # "pending" | "running" | "done" | "failed"
    "created_at": str,
}

# 意图 -> 教师模型映射（Superpower：用最强的模型教对应领域）
TEACHER_MAP = {
    "cnc_trouble":    ["deepseek_pro", "nvidia_nemotron", "claude"],
    "grbl_config":    ["deepseek_pro", "nvidia_llama70b", "longcat"],
    "gcode_help":     ["deepseek_flash", "nvidia_llama70b", "longcat_chat"],
    "embedded_dev":   ["nvidia_nemotron", "deepseek_pro", "claude"],
    "code_generation":["nvidia_qwen_coder", "deepseek_flash", "nvidia_llama70b"],
    "complex_theory": ["nvidia_nemotron", "deepseek_pro", "claude"],
    "general_cnc":    ["nvidia_llama70b", "longcat", "chinamobile"],
    "unknown":        ["nvidia_llama70b", "deepseek_flash", "longcat_chat"],
}

def check_gpu_idle(util_threshold: int = 30, mem_threshold_gb: float = 4.0,
                   window_minutes: int = 5) -> bool:
    """调用 nvidia-smi 检测 GPU 空闲状态。
    滑动窗口均值 < util_threshold 且显存占用 < mem_threshold_gb 返回 True。
    """

def build_job_queue(max_jobs: int = 100) -> list[DistillJob]:
    """构建优先级队列：
    1. 读 D:/GIT/data/distill_queue/pending/ 中的用户日志低置信度条目（priority=1.0）
    2. 从 156K 数据随机采样问题变体（priority=0.6）
    3. 合成题（priority=0.3）
    按 priority 降序排列。
    """

def run_batch(jobs: list[DistillJob], concurrency: int = 3) -> list[dict]:
    """并发调用教师模型，返回 QAPair 列表。
    使用 concurrent.futures.ThreadPoolExecutor。
    每个 job 调用 TEACHER_MAP 中的3个后端，结果写入 QAPair.all_answers。
    """

def save_pending(qa_pairs: list[dict], out_dir: str = "D:/GIT/data/distill_queue/completed/") -> int:
    """将 QAPair 列表写入 Parquet 文件，返回写入条数。
    文件名格式：{date}_{job_id[:8]}.parquet
    """

def run_idle_loop(interval_seconds: int = 60) -> None:
    """主循环：每 interval_seconds 检查 GPU 空闲，空闲则触发一批蒸馏。"""
```

---

**auto_trainer.py — 自动训练触发**

职责：监控蒸馏数据积累量，达到阈值时自动触发增量 QLoRA 训练，管理训练进程。

```python
TrainConfig = {
    "mode": str,             # "incremental" | "full"
    "new_data_paths": list[str],   # 新增数据文件路径
    "old_data_sample_ratio": float, # 混入旧数据比例，默认 0.05
    "base_adapter": str,     # 继续训练的起点 adapter 路径
    "output_dir": str,       # 新 adapter 输出路径
    "max_steps": int,        # 默认 2000（增量）或 4000（全量）
    "resume_checkpoint": str | None,
}

def check_trigger(pool_dir: str = "D:/GIT/data/training_data/incremental/",
                  min_new_samples: int = 500,
                  max_days_since_last: int = 7) -> tuple[bool, str]:
    """检查是否满足训练触发条件。
    返回 (should_train, mode)，mode 为 "incremental" 或 "full"。
    新数据 >= 5% 总量时触发全量训练，否则增量。
    """

def prepare_dataset(config: TrainConfig) -> str:
    """合并新旧数据，写入临时 JSON 文件，返回文件路径。
    混入 old_data_sample_ratio 比例的旧数据防止灾难性遗忘。
    """

def start_training(config: TrainConfig) -> subprocess.Popen:
    """启动训练子进程（调用 train_model.py），返回进程对象。
    支持断点续训（resume_checkpoint 不为 None 时传入 --resume_from_checkpoint）。
    """

def get_status() -> dict:
    """返回当前训练状态：
    {"running": bool, "step": int, "max_steps": int, "loss": float, "eta_minutes": int}
    读取最新 checkpoint 的 trainer_state.json。
    """

def on_complete(output_dir: str) -> None:
    """训练完成回调：调用 model_registry.register()，然后触发 eval_loop.run_eval()。"""
```

---

**eval_loop.py — 评估循环**

职责：训练完成后自动运行评估集，对比新旧模型指标，决定是否切换激活版本。

```python
EvalResult = {
    "version": str,
    "adapter_path": str,
    "timestamp": str,
    "domain_scores": {
        "grbl_config": float,    # GRBL 参数题准确率
        "cnc_trouble": float,    # CNC 故障诊断准确率
        "embedded_dev": float,   # 嵌入式开发准确率
    },
    "overall": float,            # 三域加权均值
    "passed": bool,              # 是否优于当前激活版本
    "rollback_reason": str | None,
}

def run_eval(adapter_path: str,
             eval_set_path: str = "D:/GIT/data/eval/eval_set.json") -> EvalResult:
    """加载 adapter，对 200 题评估集逐题推理，按域统计准确率。
    评估集格式：[{"query": str, "answer": str, "intent": str, "keywords": list[str]}]
    准确率 = 回答中包含 keywords 中至少一个关键词的比例。
    """

def compare(new: EvalResult, history_path: str = "D:/GIT/data/eval/results/") -> bool:
    """对比新版本与当前激活版本：
    - 新 overall >= 旧 overall
    - 且无单域下降 > 5%
    两个条件都满足才返回 True。
    """

def promote_if_better(new_result: EvalResult) -> bool:
    """如果 compare() 为 True，调用 model_registry.promote()，返回是否升级。"""

def append_history(result: EvalResult) -> None:
    """追加写入 D:/GIT/data/eval/results/{version}.json。"""
```

### 4.3 存储结构

```
D:/GIT/data/
├── distill_queue/
│   ├── pending/          # 待蒸馏的低质量回答
│   └── completed/        # 已蒸馏完成的数据
├── training_data/
│   ├── round7_base.json  # 当前训练基础数据 (156,414条)
│   └── incremental/      # 增量蒸馏数据（按日期）
├── models/
│   ├── registry.json     # 模型版本注册表
│   └── checkpoints/      # 各轮次检查点
└── eval/
    ├── eval_set.json     # 固定评估集 (200条)
    └── results/          # 历次评估结果
```

### 4.4 实现优先级

| 顺序 | 模块 | 原因 |
|------|------|------|
| 1 | quality_gate.py | 数据质量是一切的基础，先有门控才能保证后续数据可信 |
| 2 | model_registry.py | 版本管理是安全迭代的前提，防止训练失败无法回滚 |
| 3 | distill_scheduler.py | 有了质量门控和版本管理，才能安全地积累蒸馏数据 |
| 4 | auto_trainer.py | 数据积累到一定量后才需要自动触发训练 |
| 5 | eval_loop.py | 训练完成后才需要自动评估 |
| 6 | 闭环集成 | 五个模块全部就绪后，接入 smart_router.py 的反馈队列 |

---

## 5. 本地模型训练

### 5.1 训练配置

| 参数 | 值 |
|------|-----|
| 基座模型 | Qwen3-8B |
| 训练框架 | swift (ms-swift) |
| 量化方式 | NF4 4-bit 双量化 (bitsandbytes) |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| 序列长度 | 4096 tokens |
| 有效批次大小 | 8（batch=1 × gradient_accumulation=8） |
| 学习率 | 2e-4（cosine 衰减） |
| 硬件 | RTX 5060 Ti 16GB，Windows 11 |
| 推理部署 | LM Studio，监听 http://localhost:1234 |

### 5.2 训练数据来源

| 来源 | 数量 | 采集方式 |
|------|------|---------|
| StackExchange | 部分 | API 爬取 CNC/嵌入式相关问答 |
| 知乎 | 部分 | collect_zhihu_data.py 采集 |
| GRBL 源码蒸馏 | 部分 | extract_grbl_training.py 从源码提取参数/错误码/报警码 |
| 本地代码蒸馏 | 部分 | distill_local_code.py 从本地项目提取实现细节 |
| Claude 专家问答 | 部分 | distill_triple.py 三路蒸馏（Claude + DeepSeek + GPT） |
| **合计** | **156,414 条** | |

### 5.3 训练历史

| 轮次 | 基座 | 数据量 | 方法 | 状态 | 备注 |
|------|------|--------|------|------|------|
| Round 1 | Qwen2.5-7B-Instruct | 98,654 | SFT QLoRA | 已完成 | 初始版本 |
| Round 2 | Qwen2.5-7B-Instruct | 206,796 | SFT QLoRA | 已完成 | 数据翻倍 |
| Round 3 | Qwen2.5-7B-Instruct | 208,317 | SFT QLoRA | 已完成 | 90%完成 |
| Round 4 | Qwen3-8B | 208K+蒸馏 | SFT QLoRA | 已完成 | 切换基座 |
| Round 5 | Qwen3-8B | 156K+ | SFT QLoRA | 已完成 | |
| Round 6 | Qwen3-8B | 156K+ | SFT QLoRA | 已完成 | |
| Round 7 | Qwen3-8B | 156K+ | SFT QLoRA | 进行中 | step 1400/4000, loss=1.35 |

注：trainer_state.json 未在仓库中找到，Round 1-6 的具体 loss 曲线数据不可用。Round 7 数据来自用户提供的背景信息。

---

## 6. API 配置

### 6.1 已接入的 API

| 服务商 | URL | 模型 | 环境变量 | 备注 |
|--------|-----|------|---------|------|
| Claude (right.codes) | https://right.codes/claude-aws/v1/messages | claude-sonnet-4-6 | CLAUDE_API_KEY | Anthropic格式，x-api-key认证 |
| LongCat | https://api.longcat.chat/anthropic/v1/messages | LongCat-Flash-* | LONGCAT_API_KEY | Anthropic格式，Bearer认证 |
| DeepSeek | https://api.deepseek.com/anthropic/v1/messages | deepseek-v4-pro/flash | DEEPSEEK_API_KEY | Anthropic格式 |
| Nvidia NIM | https://integrate.api.nvidia.com/v1/chat/completions | llama/qwen/mistral/phi | NVIDIA_API_KEY | OpenAI格式，免费额度 |
| 中国移动MaaS | https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1/chat/completions | minimax-m25 | CHINAMOBILE_API_KEY | OpenAI格式 |
| 本地 LM Studio | http://localhost:1234/v1/chat/completions | local-model | 无需key | OpenAI格式 |

### 6.2 .env 配置说明

```bash
# 必填：Claude API（通过 right.codes 代理）
CLAUDE_API_KEY=

# 必填：LongCat API
LONGCAT_API_KEY=

# 推荐：DeepSeek API（CNC故障诊断主力）
DEEPSEEK_API_KEY=

# 推荐：Nvidia NIM（免费额度，代码生成/嵌入式主力）
NVIDIA_API_KEY=

# 可选：中国移动 MaaS（通用兜底）
CHINAMOBILE_API_KEY=

# 可选：对外展示的模型名（默认 red V1flash）
PUBLIC_MODEL_NAME=red V1flash

# 可选：调试模式，显示路由详情和Prompt扩写
RED_DEBUG=0
```

---

## 7. 运行指南

### 7.1 快速启动

```bash
# 1. 安装依赖
pip install python-dotenv

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入真实 API Key

# 3. 启动本地推理（可选，用于 GRBL/GCode 本地回答）
lms server start
lms load qwen3-8b

# 4. 运行智能路由器（交互式 CLI）
python D:/GIT/smart_router.py

# 5. 调试模式（显示路由详情）
RED_DEBUG=1 python D:/GIT/smart_router.py
```

### 7.2 CLI 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--query` / `-q` | 单次查询模式 | `--query "GRBL $100 怎么设置"` |
| `--backend` / `-b` | 指定后端 | `--backend claude` |
| `--json` | 输出 JSON（配合 --query） | `--query "..." --json` |
| `--test` | 测试所有后端连通性 | `--test` |
| `--pressure-test` | 对所有后端压力测试 | `--pressure-test` |
| `--backends` | 指定压力测试后端（逗号分隔） | `--backends nvidia_nemotron,claude` |
| `--status` | 显示熔断器状态 | `--status` |
| `--mcp` | 以 MCP stdio 服务模式运行 | `--mcp` |

### 7.3 压力测试

```bash
# 测试所有有效后端
python D:/GIT/smart_router.py --pressure-test

# 测试指定后端
python D:/GIT/smart_router.py --pressure-test --backends nvidia_nemotron,deepseek_pro,claude
```

结果解读：
- `STABLE`：成功率 >= 80%，可信赖
- `UNSTABLE`：成功率 50-79%，谨慎使用
- `UNRELIABLE`：成功率 < 50%，建议从降级链移除

测试使用 5 条固定查询，并发度 3，默认 5 轮。压力测试结束后自动重置熔断器状态。

---

## 8. 商业化定位

red V1flash 定位为 CNC/嵌入式领域的 AI 助手服务，面向数控机床操作员、嵌入式开发者和 CNC 设备厂商。商业模式是提供比通用大模型更精准的领域回答，同时通过智能路由控制 API 成本（优先使用免费的 Nvidia NIM 额度，付费 API 仅在必要时调用）。项目不对外宣称自研大模型，核心竞争力在于领域数据积累、路由策略优化和持续的蒸馏训练闭环。





