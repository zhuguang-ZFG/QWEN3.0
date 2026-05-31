"""Telegram programming automation commands."""

from __future__ import annotations

import logging
import subprocess

import http_caller
import telegram_bot
from routes.quality_gate_tiers import default_route
from safe_command import UnsafeCommandError, run_safe_command

logger = logging.getLogger(__name__)

TELEGRAM_TEST_COMMAND_ALLOWLIST = {
    "python",
    "python.exe",
    "pytest",
    "pytest.exe",
    "ruff",
    "ruff.exe",
    "pyright",
    "pyright.exe",
    "npm",
    "npm.cmd",
    "node",
    "node.exe",
}

GIT_COMMANDS = {
    "status_short": ["git", "status", "--short"],
    "diff_stat": ["git", "diff", "--stat"],
    "diff": ["git", "diff"],
    "log_recent": ["git", "log", "--oneline", "-10"],
    "log_ship": ["git", "log", "--oneline", "-5"],
    "branch": ["git", "branch", "--show-current"],
}


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
            "Usage:\n"
            "/code run <prompt>  - create a coding-task implementation plan\n"
            "/code plan          - analyze repo and create a plan\n"
            "/code test [cmd]    - run an allowlisted test command and analyze it\n"
            "/code review        - review current git diff\n"
            "/code ship          - check ship readiness",
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

        backend = default_route(prompt, ide="telegram_code")
        result = http_caller.call_api(backend, messages=messages, max_tokens=max_tokens)
        return result or "(no response)"
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return f"LLM call failed: {exc}"


def _run_git(name: str) -> str:
    """Run a fixed git command and return output."""
    try:
        result = subprocess.run(GIT_COMMANDS[name], capture_output=True, text=True, timeout=30, check=False)
        return result.stdout[:5000] or result.stderr[:1000] or "(no output)"
    except Exception as exc:
        return f"git error: {exc}"


async def _handle_code_run(chat_id: str, prompt: str) -> None:
    """Execute a coding task via LLM agent."""
    if not prompt:
        await telegram_bot.send_message("Usage: /code run <prompt>", chat_id=chat_id)
        return

    await telegram_bot.send_message(f"Preparing coding task: {prompt[:100]}...", chat_id=chat_id)
    system = (
        "You are a senior coding assistant. Analyze the requested coding task, "
        "propose concrete implementation steps, identify files likely to change, "
        "and include verification commands. Answer in Chinese."
    )
    answer = await _call_llm(prompt, system=system, max_tokens=8192)
    await telegram_bot.send_message(answer, chat_id=chat_id)


async def _handle_code_plan(chat_id: str, arg: str) -> None:
    """LLM analyzes repo and creates a plan."""
    await telegram_bot.send_message("Analyzing repository...", chat_id=chat_id)

    git_status = _run_git("status_short")
    git_diff_stat = _run_git("diff_stat")
    git_log = _run_git("log_recent")
    branch = _run_git("branch").strip()

    project_context = ""
    for filename in ["AGENTS.md", "CLAUDE.md"]:
        try:
            with open(filename, encoding="utf-8") as fh:
                project_context += f"\n--- {filename} ---\n" + fh.read()[:3000]
        except FileNotFoundError:
            pass

    system = (
        "You are a senior software architect. Produce a scoped implementation plan "
        "from repository state. Include goal, current state, steps, risks, and verification. "
        "Answer in Chinese."
    )
    prompt = (
        f"Branch: {branch}\n\n"
        f"Git status:\n{git_status[:2000]}\n\n"
        f"Git diff stat:\n{git_diff_stat[:1000]}\n\n"
        f"Recent commits:\n{git_log[:1000]}\n\n"
        f"{project_context}\n\n"
        "Please analyze the current repository state and create an implementation plan."
    )
    answer = await _call_llm(prompt, system=system, max_tokens=4096)
    await telegram_bot.send_message(answer, chat_id=chat_id)


async def _handle_code_test(chat_id: str, cmd: str) -> None:
    """Run tests plus LLM analysis."""
    test_cmd = cmd.strip() or "pytest --tb=short -q"
    await telegram_bot.send_message(f"Running test command: {test_cmd}", chat_id=chat_id)

    try:
        result = run_safe_command(test_cmd, allowed_commands=TELEGRAM_TEST_COMMAND_ALLOWLIST, timeout=300)
        stdout = result.stdout[-3000:]
        stderr = result.stderr[-1000:]
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, exit_code = "", "test command timed out after 300s", 1
    except UnsafeCommandError as exc:
        stdout, stderr, exit_code = "", f"unsafe command rejected: {exc}", 1
    except Exception as exc:
        stdout, stderr, exit_code = "", str(exc), 1

    system = (
        "You are a test-result reviewer. Analyze whether the test passed, summarize failures, "
        "and propose fixes or next checks. Answer in Chinese."
    )
    prompt = (
        f"Command: {test_cmd}\n"
        f"Exit code: {exit_code}\n\n"
        f"stdout:\n{stdout}\n\n"
        f"stderr:\n{stderr}\n\n"
        "Please analyze the test result."
    )
    answer = await _call_llm(prompt, system=system, max_tokens=4096)
    await telegram_bot.send_message(answer, chat_id=chat_id)


async def _handle_code_review(chat_id: str, arg: str) -> None:
    """LLM reviews current git diff."""
    await telegram_bot.send_message("Generating code review...", chat_id=chat_id)

    diff = _run_git("diff")
    diff_stat = _run_git("diff_stat")
    if not diff.strip():
        await telegram_bot.send_message("No uncommitted diff found.", chat_id=chat_id)
        return

    system = (
        "You are a senior code reviewer. Prioritize bugs, regressions, security issues, "
        "and missing tests. Answer in Chinese."
    )
    prompt = f"Diff stat:\n{diff_stat[:1000]}\n\nFull diff:\n{diff[:6000]}\n\nPlease review this diff."
    answer = await _call_llm(prompt, system=system, max_tokens=4096)
    await telegram_bot.send_message(answer, chat_id=chat_id)


async def _handle_code_ship(chat_id: str, arg: str) -> None:
    """LLM checks ship readiness."""
    await telegram_bot.send_message("Checking ship readiness...", chat_id=chat_id)

    git_status = _run_git("status_short")
    diff_stat = _run_git("diff_stat")
    git_log = _run_git("log_ship")
    branch = _run_git("branch").strip()

    try:
        result = run_safe_command(
            "pytest --tb=line -q",
            allowed_commands=TELEGRAM_TEST_COMMAND_ALLOWLIST,
            timeout=120,
        )
        combined = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-5:])
        test_output = combined[-1000:]
    except Exception:
        test_output = "(test command unavailable)"

    system = (
        "You are a release-readiness reviewer. Evaluate uncommitted changes, tests, "
        "risks, and whether the code can be shipped. Answer in Chinese."
    )
    prompt = (
        f"Branch: {branch}\n"
        f"Uncommitted changes:\n{git_status[:1000]}\n\n"
        f"Diff stat:\n{diff_stat[:500]}\n\n"
        f"Recent commits:\n{git_log[:500]}\n\n"
        f"Test result tail:\n{test_output[:1000]}\n\n"
        "Please evaluate ship readiness."
    )
    answer = await _call_llm(prompt, system=system, max_tokens=2048)
    await telegram_bot.send_message(answer, chat_id=chat_id)
