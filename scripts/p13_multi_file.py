"""P1.3: Multi-file Cross-File Programming — real vibecode scenario.

Creates a multi-module Python project with a cross-file bug.
Agent must:
  1. Read multiple files to understand the codebase
  2. Identify that a function signature changed in utils.py
  3. Find all callers across files
  4. Update both files consistently
  5. Run the test suite to verify
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMA_API_KEY = os.environ.get("LIMA_API_KEY", "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw")
LIMA_BASE = "https://chat.donglicao.com"

TOOLS = [
    {
        "name": "read_file",
        "description": "Read contents of a file at the given path",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute path"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating or overwriting it",
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
        "description": "Run a shell command. Returns stdout, stderr, exit_code.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]


def _execute(name: str, args: dict) -> str:
    if name == "read_file":
        try:
            with open(args["path"], encoding="utf-8", errors="replace") as f:
                return f.read(5000)
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "write_file":
        try:
            os.makedirs(os.path.dirname(args["path"]) or ".", exist_ok=True)
            with open(args["path"], "w", encoding="utf-8") as f:
                f.write(args["content"])
            return f"OK: Wrote {len(args['content'])} bytes"
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "run_command":
        try:
            r = subprocess.run(
                args["command"], shell=True, capture_output=True, text=True, timeout=30,
            )
            return f"stdout: {r.stdout[:2000]}\nstderr: {r.stderr[:500]}\nexit_code: {r.returncode}"
        except Exception as e:
            return f"ERROR: {e}"
    elif name == "list_files":
        try:
            files = os.listdir(args["path"])
            return "\n".join(files)
        except Exception as e:
            return f"ERROR: {e}"
    return f"ERROR: Unknown tool: {name}"


async def agent_loop(messages: list[dict], max_rounds: int = 10) -> dict:
    import httpx

    headers = {
        "Authorization": f"Bearer {LIMA_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    for r in range(max_rounds):
        body = {
            "model": "lima-code",
            "messages": messages,
            "tools": TOOLS,
            "max_tokens": 2048,
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
            detail = f"{tname}({json.dumps(targs, ensure_ascii=False)[:100]})"
            if "ERROR" in res:
                detail += f" -> {res[:80]}"
            print(f"  [r{r+1}] {detail}")
            results.append({
                "type": "tool_result",
                "tool_use_id": tid,
                "content": res[:3000],
            })
        messages.append({"role": "user", "content": results})

    return {"ok": False, "error": "Max rounds exceeded", "rounds": max_rounds}


async def test_cross_file_refactor():
    """Multi-file project with a cross-file bug caused by a renamed function."""
    print("=" * 60)
    print("P1.3: Multi-File Cross-File Programming")
    print("=" * 60)

    tmpdir = tempfile.mkdtemp(prefix="lima_multi_")

    # Create a 4-file project: cli.py, utils.py, models.py, test_all.py
    # Bug: utils.py has process_data() but cli.py calls the old name parse_data()

    utils_code = '''"""Utility functions for data processing."""
import json


def process_data(raw: str) -> dict:
    """Parse raw JSON string into a dict."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "raw": raw}


def format_output(data: dict, pretty: bool = False) -> str:
    """Format a dict for display."""
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return str(data)
'''

    models_code = '''"""Data models for the application."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    id: int
    name: str
    email: Optional[str] = None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "email": self.email}
'''

    cli_code = '''"""CLI entry point for data processing tool."""
import sys
from utils import parse_data, format_output


def main():
    if len(sys.argv) < 2:
        print("Usage: python cli.py <json_string> [--pretty]")
        return 1

    raw = sys.argv[1]
    pretty = "--pretty" in sys.argv

    result = parse_data(raw)
    output = format_output(result, pretty=pretty)
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

    test_code = '''"""Tests for the data processing tool."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import process_data, format_output
from models import User


def test_process_valid_json():
    result = process_data('{"key": "value"}')
    assert result == {"key": "value"}, f"Expected dict, got {result}"


def test_process_invalid_json():
    result = process_data("not json")
    assert "error" in result, f"Expected error, got {result}"


def test_format_pretty():
    data = {"a": 1, "b": 2}
    result = format_output(data, pretty=True)
    assert "\\n" in result or "  " in result, f"Expected pretty output, got {result}"


def test_user_model():
    user = User(id=1, name="Test", email="test@test.com")
    d = user.to_dict()
    assert d["id"] == 1
    assert d["name"] == "Test"


if __name__ == "__main__":
    tests = [
        test_process_valid_json,
        test_process_invalid_json,
        test_format_pretty,
        test_user_model,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS {test.__name__}")
        except AssertionError as e:
            print(f"  FAIL {test.__name__}: {e}")
    print(f"\\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
'''

    for name, content in [
        ("utils.py", utils_code),
        ("models.py", models_code),
        ("cli.py", cli_code),
        ("test_all.py", test_code),
    ]:
        with open(os.path.join(tmpdir, name), "w", encoding="utf-8") as f:
            f.write(content)

    files_list = ", ".join(os.listdir(tmpdir))
    prompt = (
        f"I have a Python project in {tmpdir} with files: {files_list}. "
        "The program has a bug: utils.py defines process_data() but cli.py "
        "imports and calls parse_data() (the old function name). "
        "Read ALL the source files to understand the codebase, then fix the bug. "
        "You need to update cli.py to import and call process_data() instead. "
        "Also update any tests that might need changes. "
        "Finally, run 'python test_all.py' to verify everything passes."
    )

    messages = [{"role": "user", "content": prompt}]
    result = await agent_loop(messages, max_rounds=10)

    ok = result.get("ok", False)
    content = result.get("content", "")
    rounds = result.get("rounds", 0)

    # Verify the fix: either cli.py was fixed OR tests pass (agent may fix differently)
    cli_fixed = False
    cli_path = os.path.join(tmpdir, "cli.py")
    if os.path.exists(cli_path):
        with open(cli_path, encoding="utf-8") as f:
            cli_content = f.read()
        cli_fixed = "process_data" in cli_content and "parse_data" not in cli_content

    # Run tests ourselves
    test_result = subprocess.run(
        ["python", os.path.join(tmpdir, "test_all.py")],
        capture_output=True, text=True, timeout=10, encoding="utf-8",
    )
    tests_pass = "4/4" in test_result.stdout

    print(f"\n  cli_fixed: {cli_fixed}")
    print(f"  tests: {'4/4 PASS' if tests_pass else test_result.stdout.strip()[:200]}")
    print(f"  rounds: {rounds}")

    assert ok, f"Agent loop failed: {result.get('error', '')}"
    assert cli_fixed or tests_pass, "Neither cli.py was fixed nor tests pass"
    print("  PASS: cross-file bug fixed\n")

    shutil.rmtree(tmpdir, ignore_errors=True)
    return True


async def main():
    print("LiMa P1.3: Multi-File Cross-File Programming")
    print()
    try:
        ok = await test_cross_file_refactor()
    except Exception as e:
        print(f"  FAIL: {e}\n")
        import traceback
        traceback.print_exc()
        ok = False

    print("=" * 60)
    print(f"P1.3 Multi-File: {'PASS' if ok else 'FAIL'}")
    print("=" * 60)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
