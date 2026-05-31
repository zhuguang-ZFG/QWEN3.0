"""fix_loop.py — Automated test→fail→fix→pass cycle with checkpoint safety.

When the agent makes changes and tests fail:
  1. Read test error output
  2. Read modified files
  3. Fix the code
  4. Re-run tests
  5. Repeat until pass (max 3 rounds)
  6. On persistent failure, rollback to last checkpoint

Used by vibecode agent scripts and the /lima fix command flow.
"""
from __future__ import annotations

import logging

from safe_command import UnsafeCommandError, run_safe_command

_log = logging.getLogger(__name__)

MAX_FIX_ROUNDS = 3
TEST_COMMAND_ALLOWLIST = {
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


async def fix_loop(
    test_command: str,
    modified_files: list[str],
    prompt_fn,  # async (messages) -> dict with {ok, content, tool_calls}
    execute_tool_fn,  # (name, args) -> str
    cwd: str | None = None,
    max_rounds: int = MAX_FIX_ROUNDS,
) -> dict:
    """Run test→fix→pass loop on modified files.

    Args:
        test_command: shell command to run tests
        modified_files: files that were changed (for context + rollback)
        prompt_fn: async function that calls the AI with tools
        execute_tool_fn: executes tool calls (read, write, run)
        cwd: working directory
        max_rounds: max fix attempts before giving up

    Returns:
        {ok, rounds, test_output, final_content}
    """
    from checkpoint import checkpoint_files

    # Snapshot before starting
    checkpoint_files(modified_files, reason="pre_fix_loop")

    for round_num in range(1, max_rounds + 1):
        _log.info("Fix loop round %d/%d", round_num, max_rounds)

        # Run tests
        try:
            test_result = run_safe_command(
                test_command,
                allowed_commands=TEST_COMMAND_ALLOWLIST,
                timeout=120,
                cwd=cwd,
            )
        except UnsafeCommandError as exc:
            return {"ok": False, "rounds": round_num, "error": f"unsafe test command rejected: {exc}"}
        test_output = test_result.stdout[-3000:] + test_result.stderr[-2000:]

        if test_result.returncode == 0:
            _log.info("Tests pass after %d round(s)", round_num)
            return {
                "ok": True,
                "rounds": round_num,
                "test_output": test_output,
                "final_content": "All tests passing.",
            }

        # Tests failed — ask AI to fix
        _log.info("Tests failed (exit %d), asking AI to fix...", test_result.returncode)

        fix_prompt = (
            f"Tests failed with exit code {test_result.returncode}.\n\n"
            f"Test output:\n```\n{test_output[:2000]}\n```\n\n"
            f"Modified files: {', '.join(modified_files)}\n\n"
            f"Read the failing files, understand the errors, and fix the code. "
            f"Then run `{test_command}` to verify."
        )

        messages = [{"role": "user", "content": fix_prompt}]
        result = await prompt_fn(messages)
        if not result.get("ok"):
            return {"ok": False, "rounds": round_num, "error": result.get("error", "AI call failed")}

        # Re-check test after fix
        try:
            test_result2 = run_safe_command(
                test_command,
                allowed_commands=TEST_COMMAND_ALLOWLIST,
                timeout=120,
                cwd=cwd,
            )
        except UnsafeCommandError as exc:
            return {"ok": False, "rounds": round_num, "error": f"unsafe test command rejected: {exc}"}
        if test_result2.returncode == 0:
            return {
                "ok": True,
                "rounds": round_num + 1,
                "test_output": test_result2.stdout[-1000:],
                "final_content": result.get("content", ""),
            }

    # All rounds exhausted — rollback
    _log.warning("Fix loop exhausted after %d rounds, rolling back", max_rounds)
    from checkpoint import rollback as do_rollback

    restored = do_rollback()
    return {
        "ok": False,
        "rounds": max_rounds,
        "error": f"Could not fix after {max_rounds} rounds",
        "rolled_back": len(restored),
        "final_content": "Changes rolled back to last safe checkpoint.",
    }
