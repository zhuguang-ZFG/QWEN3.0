"""P1.1: Multi-round tool error recovery — agent self-corrects after tool failures.

Tests that the agent can:
  1. Encounter a failed tool call (file not found, command error)
  2. Diagnose the problem from the error message
  3. Retry with corrected parameters
  4. Complete the task successfully
"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from safe_command import UnsafeCommandError, run_safe_command

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMA_API_KEY = os.environ.get("LIMA_API_KEY")
LIMA_BASE = "https://chat.donglicao.com"
COMMAND_ALLOWLIST = {"python", "python.exe", "pytest", "pytest.exe"}

TOOLS = [
    {
        "name": "read_file",
        "description": "Read contents of a file at the given path",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
]


def _execute(name: str, args: dict) -> str:
    if name == "read_file":
        try:
            with open(args["path"], encoding="utf-8") as f:
                return f.read(3000)
        except FileNotFoundError:
            return f"ERROR: File not found: {args['path']}"
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "write_file":
        try:
            os.makedirs(os.path.dirname(args["path"]) or ".", exist_ok=True)
            with open(args["path"], "w", encoding="utf-8") as f:
                f.write(args["content"])
            return f"OK: Wrote {len(args['content'])} bytes to {args['path']}"
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "run_command":
        try:
            r = run_safe_command(
                args["command"],
                allowed_commands=COMMAND_ALLOWLIST,
                timeout=30,
                cwd=PROJECT_ROOT,
            )
            out = f"stdout: {r.stdout[:1000]}"
            if r.stderr:
                out += f"\nstderr: {r.stderr[:300]}"
            out += f"\nexit_code: {r.returncode}"
            return out
        except UnsafeCommandError as e:
            return f"ERROR: unsafe command rejected: {e}"
        except Exception as e:
            return f"ERROR: {e}"
    return f"ERROR: Unknown tool: {name}"


async def agent_loop(messages: list[dict], max_rounds: int = 8) -> dict:
    import httpx

    headers = {
        "Authorization": f"Bearer {LIMA_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    for r in range(max_rounds):
        body = {
            "model": "code",
            "messages": messages,
            "tools": TOOLS,
            "max_tokens": 1024,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{LIMA_BASE}/v1/messages", headers=headers, json=body,
            )
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "rounds": r}

        data = resp.json()
        blocks = data.get("content", [])
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]
        text_parts = [b["text"] for b in blocks if b.get("type") == "text"]

        if not tool_blocks:
            return {
                "ok": True,
                "content": "\n".join(text_parts),
                "backend": data.get("model", "?"),
                "rounds": r + 1,
            }

        messages.append({"role": "assistant", "content": blocks})
        results = []
        for tb in tool_blocks:
            tname = tb["name"]
            targs = tb.get("input", {})
            tid = tb["id"]
            res = _execute(tname, targs)
            print(f"  [r{r+1}] {tname}({json.dumps(targs, ensure_ascii=False)[:100]})")
            # Show error if any
            if "ERROR:" in res:
                print(f"         -> {res[:120]}")
            results.append({
                "type": "tool_result",
                "tool_use_id": tid,
                "content": res[:3000],
            })
        messages.append({"role": "user", "content": results})

    return {"ok": False, "error": "Max rounds exceeded", "rounds": max_rounds}


async def test_error_recovery():
    """Agent should recover when first tool call hits a wrong path."""
    print("=" * 60)
    print("P1.1: Multi-round Error Recovery")
    print("=" * 60)

    tmpdir = tempfile.mkdtemp(prefix="lima_errrec_")
    config_file = os.path.join(tmpdir, "config.json")
    correct_content = '{"version": "2.0", "debug": false}'
    with open(config_file, "w") as f:
        f.write(correct_content)

    # Deliberately give a WRONG path to trigger error → recovery
    wrong_path = os.path.join(tmpdir, "confg.json")  # typo: missing 'i'

    prompt = (
        f"Read the config file at {wrong_path} and tell me the version. "
        "If the file is not found, try the correct path instead. "
        "The actual file is named config.json in the same directory."
    )

    messages = [{"role": "user", "content": prompt}]
    result = await agent_loop(messages, max_rounds=5)

    ok = result.get("ok", False)
    content = result.get("content", "")
    rounds = result.get("rounds", 0)
    recovered = "2.0" in content or "version" in content.lower()

    print(f"  result: ok={ok} rounds={rounds}")
    print(f"  recovered: {recovered}")
    print(f"  content: {content[:200]}")

    # Must recover from the intentional wrong path
    assert ok, f"Agent loop failed: {result.get('error', '')}"
    # The agent should have tried read_file at least twice (wrong path → correct path)
    assert rounds >= 2, f"No retry attempted (rounds={rounds})"
    print("  PASS: agent recovered from error\n")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    return True


async def test_syntax_fix():
    """Agent should fix a Python syntax error reported by run_command."""
    print("=" * 60)
    print("P1.1: Syntax Error Self-Fix")
    print("=" * 60)

    tmpdir = tempfile.mkdtemp(prefix="lima_synfix_")
    broken_file = os.path.join(tmpdir, "script.py")

    # Write a Python file with a deliberate syntax error
    with open(broken_file, "w") as f:
        f.write("def hello()\n    print('missing colon on line above')\n")

    prompt = (
        f"Run 'python {broken_file}' to check the script. "
        "If it has a syntax error, fix the file and run it again to verify."
    )

    messages = [{"role": "user", "content": prompt}]
    result = await agent_loop(messages, max_rounds=6)

    ok = result.get("ok", False)
    content = result.get("content", "")
    rounds = result.get("rounds", 0)

    # Check if the file was fixed
    fixed = False
    if os.path.exists(broken_file):
        with open(broken_file) as f:
            code = f.read()
        fixed = "def hello():" in code  # Should have added the colon

    print(f"  result: ok={ok} rounds={rounds}")
    print(f"  syntax_fixed: {fixed}")
    print(f"  content: {content[:200]}")

    assert ok, f"Agent loop failed: {result.get('error', '')}"
    assert fixed, "Syntax error was not fixed"
    print("  PASS: syntax error self-fixed\n")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    return True


async def main():
    if not LIMA_API_KEY:
        raise SystemExit("LIMA_API_KEY env var is required")

    print("LiMa P1.1: Multi-round Tool Error Recovery")
    print()

    results = []
    for test_fn in [test_error_recovery, test_syntax_fix]:
        try:
            results.append(await test_fn())
        except Exception as e:
            print(f"  FAIL: {e}\n")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(results)
    print("=" * 60)
    print(f"P1.1 Error Recovery: {passed}/{len(results)} passed")
    print("=" * 60)
    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
