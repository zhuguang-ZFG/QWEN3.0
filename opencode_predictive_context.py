"""opencode_predictive_context.py — 预测性上下文加载。

根据 OpenCode 请求中的文件路径、import 语句、错误堆栈等线索，预测可能需要的相关文件，
提前加载到上下文中。这样 LLM 在后续工具调用时有更完整的项目理解。

使用场景:
- 用户提到 "Fix server.py line 42" → 预加载 server.py 周边的 import 依赖
- 错误堆栈包含多个文件 → 预加载调用链中的所有文件
- 用户要求 "重构 UserService" → 预加载相关的 model、controller、test 文件

设计原则:
- 轻量级：只做快速文本分析，不运行静态分析工具
- 可选：预加载失败不应影响主流程
- 异步：在后台预加载，不阻塞主响应
- 限额：最多预加载 5 个文件，避免上下文污染

注意：这是实验性功能，默认禁用。通过环境变量 LIMA_OPENCODE_PREDICTIVE_CONTEXT=1 启用。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)

# 配置参数
ENABLED = os.environ.get("LIMA_OPENCODE_PREDICTIVE_CONTEXT", "0") == "1"
MAX_PREDICTIVE_FILES = 5
MAX_FILE_SIZE = 100_000  # 100KB，避免加载大文件


def extract_file_mentions(content: str) -> list[str]:
    """从消息内容中提取文件路径引用。"""
    # 匹配常见模式：
    # - "Fix D:\GIT\server.py line 42"
    # - "server.py:42"
    # - "in routes/chat_endpoints.py"
    # - "File \"server.py\", line 42"

    patterns = [
        r'(?:Fix|Check|Update|Refactor|Edit)\s+([A-Za-z]:[/\\][\w/\\.-]+\.py)',  # 绝对路径
        r'([/\\]?[\w/\\-]+\.(?:py|js|ts|tsx|jsx|go|rs|java|cpp))\s*:\d+',  # 相对路径 + 行号
        r'(?:in|at|File)\s+"?([/\\]?[\w/\\-]+\.(?:py|js|ts|tsx|jsx))"?',  # 错误堆栈
        r'import\s+.*\s+from\s+["\']([./\w-]+)["\']',  # import 语句
    ]

    files = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        files.extend(matches)

    return list(set(files))[:MAX_PREDICTIVE_FILES]


def normalize_path(mentioned_path: str, project_root: Optional[str] = None) -> Optional[str]:
    """规范化文件路径（相对路径 → 绝对路径）。"""
    if not mentioned_path:
        return None

    # 已经是绝对路径
    if Path(mentioned_path).is_absolute():
        return mentioned_path if Path(mentioned_path).exists() else None

    # 相对路径：尝试在项目根目录下查找
    if project_root:
        full_path = Path(project_root) / mentioned_path
        if full_path.exists():
            return str(full_path)

    # 当前工作目录
    cwd_path = Path.cwd() / mentioned_path
    if cwd_path.exists():
        return str(cwd_path)

    return None


def predict_related_files(file_path: str, max_related: int = 3) -> list[str]:
    """预测相关文件（基于命名规则）。"""
    if not file_path:
        return []

    path = Path(file_path)
    if not path.exists():
        return []

    related = []
    stem = path.stem
    parent = path.parent

    # 规则 1: test 文件 ↔ 源文件
    if stem.startswith("test_"):
        source = parent / f"{stem[5:]}{path.suffix}"
        if source.exists():
            related.append(str(source))
    else:
        test = parent / f"test_{stem}{path.suffix}"
        if test.exists():
            related.append(str(test))

    # 规则 2: model ↔ controller ↔ service (Python)
    if path.suffix == ".py":
        if stem.endswith("_model"):
            controller = parent / f"{stem[:-6]}_controller.py"
            if controller.exists():
                related.append(str(controller))
        elif stem.endswith("_controller"):
            model = parent / f"{stem[:-11]}_model.py"
            service = parent / f"{stem[:-11]}_service.py"
            if model.exists():
                related.append(str(model))
            if service.exists():
                related.append(str(service))

    # 规则 3: index.ts ↔ 同目录下的其他 ts 文件
    if stem == "index" and path.suffix in (".ts", ".tsx", ".js", ".jsx"):
        siblings = [
            str(f) for f in parent.glob(f"*{path.suffix}")
            if f.stem != "index" and f.is_file()
        ][:2]
        related.extend(siblings)

    return related[:max_related]


def load_predictive_context(messages: list[dict], project_root: Optional[str] = None) -> list[dict]:
    """从消息中预测并加载相关文件到上下文。"""
    if not ENABLED:
        return []

    # 提取所有文件引用
    all_content = " ".join(
        msg.get("content", "") for msg in messages if isinstance(msg.get("content"), str)
    )

    mentioned_files = extract_file_mentions(all_content)
    if not mentioned_files:
        return []

    # 规范化路径
    real_paths = []
    for mentioned in mentioned_files:
        real = normalize_path(mentioned, project_root)
        if real:
            real_paths.append(real)

    # 预测相关文件
    all_paths = set(real_paths)
    for path in real_paths:
        related = predict_related_files(path, max_related=2)
        all_paths.update(related)

    # 限制数量
    all_paths = list(all_paths)[:MAX_PREDICTIVE_FILES]

    # 加载文件内容
    context_files = []
    for path in all_paths:
        try:
            file_size = Path(path).stat().st_size
            if file_size > MAX_FILE_SIZE:
                _log.debug("skip large file: %s (%d bytes)", path, file_size)
                continue

            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            context_files.append({
                "path": path,
                "content": content,
                "size": len(content),
            })
            _log.debug("predictive load: %s (%d chars)", path, len(content))

        except Exception as exc:
            _log.debug("predictive load failed: %s (%s)", path, type(exc).__name__)

    return context_files


def format_context_injection(context_files: list[dict]) -> str:
    """将预加载的文件格式化为上下文注入字符串。"""
    if not context_files:
        return ""

    lines = ["## Predictive Context (Related Files)\n"]
    for item in context_files:
        lines.append(f"### {item['path']}\n")
        lines.append(f"```\n{item['content']}\n```\n")

    return "\n".join(lines)
