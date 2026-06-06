"""P0.2: Code + Tool Joint Scenario — real vibecode read→edit→run closed loop.

Tests the full coding agent workflow:
  1. Read a broken Python file
  2. Edit to fix the bug
  3. Run the test to verify
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMA_API_KEY = os.environ.get("LIMA_API_KEY", "")
LIMA_BASE = "https://chat.donglicao.com"

ANTHROPIC_TOOLS = [
    {
        "name": "read_file",
        "description": "Read contents of a file at the given path",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute path to the file"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating or overwriting it",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to write to"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command and return stdout, stderr, and exit code",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Shell command to execute"}},
            "required": ["command"],
        },
    },
]


def _execute_tool(name: str, args: dict) -> str:
    if name == "read_file":
        try:
            with open(args["path"], encoding="utf-8") as f:
                return f.read(5000)
        except Exception as e:
            return f"Error: {e}"
    elif name == "write_file":
        try:
            os.makedirs(os.path.dirname(args["path"]) or ".", exist_ok=True)
            with open(args["path"], "w", encoding="utf-8") as f:
                f.write(args["content"])
            return f"Wrote {len(args['content'])} bytes to {args['path']}"
        except Exception as e:
            return f"Error: {e}"
    elif name == "run_command":
        try:
            r = subprocess.run(
                args["command"], shell=True, capture_output=True, text=True,
                timeout=60, cwd=PROJECT_ROOT,
            )
            return f"stdout:\n{r.stdout[:2000]}\nstderr:\n{r.stderr[:500]}\nexit_code: {r.returncode}"
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown tool: {name}"


async def agent_loop(messages: list[dict], max_rounds: int = 8) -> dict:
    """Run the tool-using agent loop against LiMa Anthropic endpoint."""
    import httpx

    headers = {
        "Authorization": f"Bearer {LIMA_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    for round_num in range(max_rounds):
        body = {
            "model": "lima",
            "messages": messages,
            "tools": ANTHROPIC_TOOLS,
            "max_tokens": 2048,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{LIMA_BASE}/v1/messages", headers=headers, json=body,
            )

        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "rounds": round_num}

        data = resp.json()
        backend = data.get("model", "?")
        content_blocks = data.get("content", [])
        stop_reason = data.get("stop_reason", "?")

        text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]
        tool_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]

        if not tool_blocks:
            return {
                "ok": True,
                "content": "\n".join(text_parts),
                "backend": backend,
                "rounds": round_num + 1,
                "stop_reason": stop_reason,
            }

        messages.append({"role": "assistant", "content": content_blocks})
        tool_results = []
        for tb in tool_blocks:
            tname = tb["name"]
            targs = tb.get("input", {})
            tid = tb["id"]
            print(f"  [round {round_num+1}] {tname}({json.dumps(targs, ensure_ascii=False)[:120]})")
            result = _execute_tool(tname, targs)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tid,
                "content": result[:3000],
            })
        messages.append({"role": "user", "content": tool_results})

    return {"ok": False, "error": "Max rounds exceeded", "rounds": max_rounds}


async def test_code_fix_scenario():
    """Create a buggy Python file, have AI fix it, and verify."""
    print("=" * 60)
    print("P0.2: Code Fix Scenario — read → edit → run → verify")
    print("=" * 60)

    tmpdir = tempfile.mkdtemp(prefix="limafix_")
    buggy_file = os.path.join(tmpdir, "calculator.py")
    test_file = os.path.join(tmpdir, "test_calculator.py")

    # Create a buggy Python file (divide-by-zero bug)
    buggy_code = '''"""Calculator with a subtle bug."""
def add(a, b):
    return a + b

def divide(a, b):
    return a / b

def average(numbers):
    total = sum(numbers)
    count = len(numbers)
    return total / count
'''
    with open(buggy_file, "w") as f:
        f.write(buggy_code)

    # Create a test file that will fail
    test_code = f'''"""Tests for calculator — empty list edge case."""
import sys
sys.path.insert(0, "{tmpdir.replace(chr(92), "/")}")
from calculator import average

# This should NOT crash with empty list
try:
    result = average([])
    print(f"FAIL: average([]) returned {{result}}, expected ZeroDivisionError")
except ZeroDivisionError:
    print("BUG CONFIRMED: ZeroDivisionError on empty list")
except Exception as e:
    print(f"FAIL: Unexpected error: {{e}}")
'''
    with open(test_file, "w") as f:
        f.write(test_code)

    # Step 1: Ask AI to find and fix the bug
    prompt = (
        f"I have a buggy calculator module at {buggy_file} and a test at {test_file}. "
        "The average() function crashes on empty lists with ZeroDivisionError. "
        "1. Read calculator.py to understand the bug "
        "2. Fix it by adding empty-list handling "
        "3. Run the test to verify the fix works"
    )

    messages = [{"role": "user", "content": prompt}]
    result = await agent_loop(messages, max_rounds=8)

    ok = result.get("ok", False)
    content = result.get("content", "")

    # Verify the fix was applied
    fixed_ok = False
    if os.path.exists(buggy_file):
        with open(buggy_file) as f:
            fixed_code = f.read()
        fixed_ok = "if not numbers" in fixed_code or "len(numbers) == 0" in fixed_code or "return 0" in fixed_code

    # Run the test ourselves to verify
    test_result = subprocess.run(
        ["python", test_file], capture_output=True, text=True, timeout=10,
    )

    print(f"  fix_applied: {fixed_ok}")
    print(f"  test_output: {test_result.stdout.strip()[:200]}")
    print(f"  backend: {result.get('backend', '?')}")
    print(f"  rounds: {result.get('rounds', '?')}")
    print(f"  content: {content[:200]}")

    assert ok, f"Agent loop failed: {result.get('error', '')}"
    assert fixed_ok, "Fix was not applied to the file"
    print("  PASS: code fix scenario\n")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    return True


async def main():
    print("LiMa P0.2: Code + Tool Joint Scenario E2E")
    print()

    results = []
    try:
        results.append(await test_code_fix_scenario())
    except Exception as e:
        print(f"  FAIL: {e}\n")
        import traceback
        traceback.print_exc()
        results.append(False)

    passed = sum(results)
    print("=" * 60)
    print(f"P0.2 Code+Tool Joint: {passed}/{len(results)} passed")
    print("=" * 60)
    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
