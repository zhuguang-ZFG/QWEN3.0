"""Telegram programming automation commands.

 /code run <prompt>  — Execute a coding task via LLM agent
 /code plan          — LLM analyzes repo and creates plan
 /code test <cmd>    — Run tests + LLM analyzes results
 /code review        — LLM reviews current git diff
 /code ship          — LLM checks ship readiness
"""

from __future__ import annotations

import logging
import subprocess

import http_caller
import telegram_bot

logger = logging.getLogger(__name__)


async def cmd_code_automation(chat_id: str, subcmd: str, arg: str) -> None:
    """Dispatch /code subcommands to LLM-powered handlers."""
    handlers = {
        "run": _handle_code_run,
        "plan": _handle_code_plan,
        "test": _handle_code_test,
        "review": _handle_code_review,
        "ship": _handle_code_ship,
    }
    handler = handlers.get(subcmd)
    if handler is None:
        await telegram_bot.send_message(
            "用法:\n"
            "/code run <描述>  — 执行编码任务\n"
            "/code plan       — LLM 分析仓库并生成计划\n"
            "/code test [命令] — 运行测试 + LLM 分析结果\n"
            "/code review     — LLM 审查当前 diff\n"
            "/code ship       — LLM 检查发布就绪状态",
            chat_id=chat_id,
        )
        return
    await handler(chat_id, arg)


async def _call_llm(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
    """Call LiMa Server LLM with a prompt and return the response."""
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        result = http_caller.call_api(
            messages=messages,
            max_tokens=max_tokens,
        )
        return result.get("answer", "") or result.get("content", "") or "(no response)"
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return f"LLM 调用失败: {exc}"


def _run_git(cmd: str) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30,
        )
        return result.stdout[:5000] or "(no output)"
    except Exception as exc:
        return f"git error: {exc}"


async def _handle_code_run(chat_id: str, prompt: str) -> None:
    """Execute a coding task via LLM agent."""
    if not prompt:
        await telegram_bot.send_message("用法: /code run <描述要做什么>", chat_id=chat_id)
        return

    await telegram_bot.send_message(f"🔄 执行中: {prompt[:100]}...", chat_id=chat_id)

    system = (
        "你是一个专业的编程助手。用户会给你一个编码任务描述。\n"
        "请：\n"
        "1. 分析任务需求\n"
        "2. 给出具体实现方案（含代码）\n"
        "3. 说明需要修改哪些文件\n"
        "4. 给出验证命令\n"
        "用中文回答，代码用 markdown 格式。"
    )
    answer = await _call_llm(prompt, system=system, max_tokens=8192)
    await telegram_bot.send_message(answer, chat_id=chat_id)


async def _handle_code_plan(chat_id: str, arg: str) -> None:
    """LLM analyzes repo and creates a plan."""
    await telegram_bot.send_message("🔄 分析仓库中...", chat_id=chat_id)

    git_status = _run_git("git status --short")
    git_diff_stat = _run_git("git diff --stat")
    git_log = _run_git("git log --oneline -10")
    branch = _run_git("git branch --show-current").strip()

    # Try to read AGENTS.md or CLAUDE.md
    project_context = ""
    for f in ["AGENTS.md", "CLAUDE.md"]:
        try:
            with open(f) as fh:
                project_context += f"\n--- {f} ---\n" + fh.read()[:3000]
        except FileNotFoundError:
            pass

    system = (
        "你是一个专业的软件架构师。基于仓库状态生成实现计划。\n"
        "输出格式：\n"
        "## 任务目标\n目标描述\n\n"
        "## 当前状态\n仓库状态摘要\n\n"
        "## 实施步骤\n1. ...\n2. ...\n\n"
        "## 风险点\n- ...\n\n"
        "## 验证方式\n- ..."
    )
    prompt = (
        f"分支: {branch}\n\n"
        f"Git Status:\n{git_status[:2000]}\n\n"
        f"Git Diff Stat:\n{git_diff_stat[:1000]}\n\n"
        f"最近提交:\n{git_log[:1000]}\n\n"
        f"{project_context}\n\n"
        f"请分析当前仓库状态并生成实现计划。"
    )
    answer = await _call_llm(prompt, system=system, max_tokens=4096)
    await telegram_bot.send_message(answer, chat_id=chat_id)


async def _handle_code_test(chat_id: str, cmd: str) -> None:
    """Run tests + LLM analyzes results."""
    test_cmd = cmd.strip() or "pytest --tb=short -q"
    await telegram_bot.send_message(f"🔄 运行测试: {test_cmd}", chat_id=chat_id)

    try:
        result = subprocess.run(
            test_cmd, shell=True, capture_output=True, text=True, timeout=300,
        )
        stdout = result.stdout[-3000:]
        stderr = result.stderr[-1000:]
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, exit_code = "", "测试超时 (300s)", 1
    except Exception as exc:
        stdout, stderr, exit_code = "", str(exc), 1

    system = (
        "你是测试分析专家。分析测试结果并给出建议。\n"
        "如果测试全部通过，确认并给出改进建议。\n"
        "如果有失败，分析失败原因并给出修复方案。\n"
        "用中文回答。"
    )
    prompt = (
        f"测试命令: {test_cmd}\n"
        f"退出码: {exit_code}\n\n"
        f"stdout:\n{stdout}\n\n"
        f"stderr:\n{stderr}\n\n"
        f"请分析测试结果。"
    )
    answer = await _call_llm(prompt, system=system, max_tokens=4096)
    await telegram_bot.send_message(answer, chat_id=chat_id)


async def _handle_code_review(chat_id: str, arg: str) -> None:
    """LLM reviews current git diff."""
    await telegram_bot.send_message("🔄 生成代码审查...", chat_id=chat_id)

    diff = _run_git("git diff")
    diff_stat = _run_git("git diff --stat")

    if not diff.strip():
        await telegram_bot.send_message("当前没有未提交的更改。", chat_id=chat_id)
        return

    system = (
        "你是资深代码审查专家。审查 git diff 并给出详细反馈。\n"
        "格式：\n"
        "## 变更摘要\n...\n\n"
        "## 问题\n- [严重/中等/轻微] ...\n\n"
        "## 建议\n- ...\n\n"
        "## 总体评价\n通过/需要修改/不通过\n"
        "用中文回答。"
    )
    prompt = (
        f"变更统计:\n{diff_stat[:1000]}\n\n"
        f"完整 diff:\n{diff[:6000]}\n\n"
        f"请审查这段代码变更。"
    )
    answer = await _call_llm(prompt, system=system, max_tokens=4096)
    await telegram_bot.send_message(answer, chat_id=chat_id)


async def _handle_code_ship(chat_id: str, arg: str) -> None:
    """LLM checks ship readiness."""
    await telegram_bot.send_message("🔄 检查发布就绪状态...", chat_id=chat_id)

    git_status = _run_git("git status --short")
    diff_stat = _run_git("git diff --stat")
    git_log = _run_git("git log --oneline -5")
    branch = _run_git("git branch --show-current").strip()

    # Try to run tests
    test_output = ""
    try:
        result = subprocess.run(
            "pytest --tb=line -q 2>&1 | tail -5",
            shell=True, capture_output=True, text=True, timeout=120,
        )
        test_output = result.stdout[-1000:]
    except Exception:
        test_output = "(测试无法运行)"

    system = (
        "你是发布检查专家。评估当前代码是否可以安全发布。\n"
        "检查项：\n"
        "1. 是否有未提交的更改\n"
        "2. 测试是否通过\n"
        "3. 是否有明显的风险\n"
        "4. 变更范围是否合理\n"
        "结论：✅ 可以发布 / ⚠️ 需要修改 / ❌ 不能发布\n"
        "用中文回答。"
    )
    prompt = (
        f"分支: {branch}\n"
        f"未提交更改:\n{git_status[:1000]}\n\n"
        f"变更统计:\n{diff_stat[:500]}\n\n"
        f"最近提交:\n{git_log[:500]}\n\n"
        f"测试结果:\n{test_output[:1000]}\n\n"
        f"请评估发布就绪状态。"
    )
    answer = await _call_llm(prompt, system=system, max_tokens=2048)
    await telegram_bot.send_message(answer, chat_id=chat_id)
