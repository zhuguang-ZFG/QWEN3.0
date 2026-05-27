# Skills 智能补缺注入设计

> 日期: 2026-05-20
> 原则: 检测具体每条 skill 是否已存在，只补缺的
> 参考: Cursor Auto Mode 逆向分析 + fabric patterns

## 零、Cursor 的做法（核心参考）

Cursor 的 Skills 系统：
- System prompt 极简（642 tokens）
- Skills 只列目录名（每个 ~2 tokens）
- AI 自己决定何时加载哪个 skill
- 加载时调用 `fetch_rules("skill-name")` 拉取完整内容
- 节省 80%+ tokens

```
System Prompt:  "Available skills: deploy-checklist, db-migration..."
When AI decides a skill is relevant:
  → calls fetch_rules("skill-name")
  → full SKILL.md content loaded
```

**我们的场景不同：** 免费弱模型没有 tool calling 能力，不能自主拉取。
所以需要**双模式**：

| 后端能力 | 策略 | 参考 |
|---------|------|------|
| 强模型 (能 tool call) | Cursor 模式 — 列目录，让模型自己拉取 | Cursor |
| 弱模型 (无 tool call) | 智能补缺 — 检测缺失，预注入最少量 | 我们的设计 |

## 一、问题

用户/IDE 可能已经在 system prompt 中包含了部分 skills：
- Claude Code 自带 8000 tok 完整编程规范
- Cursor 自带 "intelligent programmer" 指令
- 用户自己写了 "你是 Python 专家，遵循 PEP 8"

如果我们无脑追加 skills，会导致：
- 重复指令浪费 token
- 冲突指令让模型困惑
- 破坏用户精心设计的 prompt 结构

## 二、正确做法：逐条检测 + 智能补缺

### 2.1 Skills 定义为独立条目

每条 skill 是一个独立单元，有：
- `id`: 唯一标识
- `content`: 注入的文本
- `detect_keywords`: 检测是否已存在的关键词列表（OR 逻辑）
- `category`: 分类 (lang/style/safety/project)
- `priority`: 优先级 (1-5, 1最高)

```python
SKILLS_CATALOG = [
    {
        "id": "python_pep8",
        "content": "Follow PEP 8 style guide for Python code.",
        "detect_keywords": ["pep 8", "pep8", "python style"],
        "category": "lang",
        "priority": 3,
    },
    ...
]
```

### 2.2 检测逻辑（参考 rules-generator 的两阶段匹配）

```python
def detect_missing_skills(system_prompt: str, skills: list) -> list:
    """逐条检测，返回 system prompt 中缺失的 skills"""
    prompt_lower = system_prompt.lower()
    missing = []
    for skill in skills:
        # 字面量匹配: 任一关键词命中 = 已覆盖
        already_present = any(
            kw.lower() in prompt_lower
            for kw in skill["detect_keywords"]
        )
        if not already_present:
            missing.append(skill)
    return missing
```

### 2.3 注入方式（参考 fabric 的 system message 组合）

不追加到用户的 system prompt 末尾（会破坏结构），
而是作为独立的 system message 插入：

```python
def inject_skills(messages: list, missing_skills: list) -> list:
    """在 messages 开头插入补缺 skills（不修改用户原有内容）"""
    if not missing_skills:
        return messages

    skills_text = "\n".join(s["content"] for s in missing_skills)
    skills_msg = {
        "role": "system",
        "content": skills_text
    }

    # 如果第一条已经是 system，追加到其后
    # 如果没有 system，插入到最前面
    if messages and messages[0].get("role") == "system":
        return [messages[0], skills_msg] + messages[1:]
    else:
        return [skills_msg] + messages
```

### 2.4 长内容处理（参考 rules-generator 的指针系统）

```python
MAX_SKILL_TOKENS = 200  # 单条 skill 最大 token 数
MAX_TOTAL_SKILLS = 5    # 最多注入 5 条

def truncate_or_pointer(skill: dict) -> dict:
    """超长 skill 只注入描述 + 指针"""
    if len(skill["content"]) > MAX_SKILL_TOKENS * 4:  # 粗估 1 token ≈ 4 chars
        return {
            **skill,
            "content": f"[Skill: {skill['id']}] {skill['content'][:100]}..."
        }
    return skill
```

## 三、Skills 目录设计

### 3.1 按类别组织

| 类别 | 何时注入 | 示例 |
|------|---------|------|
| lang | 检测到对应语言且未覆盖 | PEP 8, Go error handling |
| style | 弱模型 + 未覆盖 | 简洁回复, 不废话 |
| safety | 弱模型 + 未覆盖 | 不幻觉, 不编造 |
| project | 永远补缺（检测后） | 我们用 FastAPI + httpx |

### 3.2 检测精度要求

- 关键词要足够具体，避免误判
- "python" 太宽泛（出现不代表覆盖了 PEP 8）
- "pep 8" / "pep8" 才是精确检测
- 多个关键词用 OR 逻辑（任一命中 = 已覆盖）

### 3.3 注入量控制

- 最多注入 5 条 skills（避免 prompt 膨胀）
- 按优先级排序：safety > lang > style > project
- 总注入文本不超过 200 token

## 四、与后端模型能力的关系

| 后端能力 | 注入策略 |
|---------|---------|
| 强模型 (GPT-4级) | 只补缺 safety + project |
| 中等模型 | 补缺 safety + lang + project |
| 弱模型 | 补缺全部类别 |

## 五、实现步骤

1. 定义 SKILLS_CATALOG（每条 skill 独立文件，如 Cursor 的 .mdc）
2. 实现 detect_missing_skills（逐条关键词检测）
3. 实现 inject_skills（独立 system message，不修改原有）
4. 集成到 v3_integration.py 的执行流程
5. 测试：验证不重复注入

## 六、双模式架构（基于 Cursor 逆向分析）

### 6.1 模式 A: 目录模式（强模型）

学 Cursor：system prompt 只列 skill 名称目录，让模型自己决定加载。

```python
# 强模型（有 tool calling 能力）
skills_directory = "Available skills: " + ", ".join(s["id"] for s in SKILLS_CATALOG)
# 注入到 system prompt 末尾，只占 ~50 tokens
# 模型需要时通过 tool call 拉取完整内容
```

适用: longcat_chat, deepseek_flash, naga_gpt41mini 等强模型

### 6.2 模式 B: 补缺模式（弱模型）

弱模型无法自主拉取，需要预注入：

```python
# 弱模型（无 tool calling）
missing = detect_missing_skills(system_prompt, relevant_skills)
# 只注入缺失的，最多 5 条，不超过 200 tokens
inject_skills(messages, missing[:5])
```

适用: chat_ubi, pollinations, unclose_hermes 等弱模型

### 6.3 模式切换逻辑

```python
STRONG_MODELS_WITH_TOOLS = {"longcat_chat", "deepseek_flash", "naga_gpt41mini"}

def apply_skills(backend: str, messages: list, system_prompt: str) -> list:
    if backend in STRONG_MODELS_WITH_TOOLS:
        # 模式 A: 只列目录
        return inject_skills_directory(messages)
    else:
        # 模式 B: 智能补缺
        missing = detect_missing_skills(system_prompt, get_relevant_skills())
        return inject_skills(messages, missing[:5])
```

### 6.4 Cursor 的关键设计启示

| Cursor 做法 | 我们的借鉴 |
|------------|-----------|
| 642 token 极简 system prompt | 不塞满，留空间给代码上下文 |
| Skills 只列目录名 | 强模型用目录模式 |
| Rules 按 glob 匹配注入 | Skills 按语言/场景匹配 |
| alwaysApply vs 条件注入 | safety 类 always，lang 类条件 |
| "万物皆文件" 按需加载 | Skills 存为独立 .md 文件 |

### 6.5 Skills 文件组织

```
skills/
├── safety/
│   ├── no_hallucination.md
│   └── honest_uncertainty.md
├── lang/
│   ├── python_pep8.md
│   ├── go_error_handling.md
│   └── js_async_patterns.md
├── style/
│   ├── concise_response.md
│   └── code_comments.md
└── project/
    └── lima_conventions.md
```

每个 .md 文件格式：
```yaml
---
id: python_pep8
category: lang
detect_keywords: ["pep 8", "pep8", "python style guide"]
always_apply: false
globs: ["*.py"]
priority: 3
---
Follow PEP 8 style guide. Use snake_case for functions and variables.
```
