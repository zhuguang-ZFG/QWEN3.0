# Skills 智能补缺注入设计

> 日期: 2026-05-20
> 原则: 检测具体每条 skill 是否已存在，只补缺的

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
- `detect_keywords`: 检测是否已存在的关键词列表
- `category`: 分类 (lang/style/safety/project)

```python
SKILLS_CATALOG = [
    {
        "id": "python_pep8",
        "content": "Follow PEP 8 style guide for Python code.",
        "detect_keywords": ["pep 8", "pep8", "python style"],
        "category": "lang",
    },
    {
        "id": "python_type_hints",
        "content": "Use type hints for function signatures.",
        "detect_keywords": ["type hint", "typing", "-> ", ": str"],
        "category": "lang",
    },
    {
        "id": "no_hallucination",
        "content": "If unsure, say so. Do not make up information.",
        "detect_keywords": ["hallucin", "make up", "不确定就说"],
        "category": "safety",
    },
    {
        "id": "error_handling",
        "content": "Handle errors explicitly, never silently swallow exceptions.",
        "detect_keywords": ["error handling", "exception", "try/except"],
        "category": "style",
    },
]
```

### 2.2 检测逻辑

```python
def detect_missing_skills(system_prompt: str, skills: list) -> list:
    """逐条检测，返回 system prompt 中缺失的 skills"""
    prompt_lower = system_prompt.lower()
    missing = []
    for skill in skills:
        already_present = any(
            kw.lower() in prompt_lower
            for kw in skill["detect_keywords"]
        )
        if not already_present:
            missing.append(skill)
    return missing
```

### 2.3 注入方式

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

1. 定义 SKILLS_CATALOG（每条 skill 独立）
2. 实现 detect_missing_skills（逐条关键词检测）
3. 实现 inject_skills（独立 system message，不修改原有）
4. 集成到 v3_integration.py 的执行流程
5. 测试：验证不重复注入
