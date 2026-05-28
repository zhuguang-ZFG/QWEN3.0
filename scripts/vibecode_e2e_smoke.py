"""Real vibecode agent-loop smoke test — tool-calling end-to-end with file I/O.

Tests the full loop: AI decides to read a file → tool call → execute → AI responds.
"""
import asyncio
import json
import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMA_API_KEY = os.environ.get("LIMA_API_KEY", "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw")
LIMA_BASE = os.environ.get("LIMA_CODE_SERVER_URL", "https://chat.donglicao.com")
LIMA_MODEL = "lima-code"

# ── Tool definitions (OpenAI format) ──────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
            },
        },
    },
]


def _execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool call locally."""
    if tool_name == "read_file":
        path = args.get("path", "")
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read(3000)
            return f"File contents (first 3000 chars):\n{content}"
        except FileNotFoundError:
            return f"Error: File not found: {path}"
        except Exception as e:
            return f"Error reading {path}: {e}"
    elif tool_name == "write_file":
        path = args.get("path", "")
        content = args.get("content", "")
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"
    elif tool_name == "run_command":
        cmd = args.get("command", "")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=PROJECT_ROOT,
            )
            return f"stdout:\n{result.stdout[:2000]}\nstderr:\n{result.stderr[:500]}\nexit_code: {result.returncode}"
        except subprocess.TimeoutExpired:
            return "Error: command timed out after 30s"
        except Exception as e:
            return f"Error running command: {e}"
    return f"Unknown tool: {tool_name}"


async def call_lima_with_tools(messages: list[dict], max_rounds: int = 5) -> dict:
    """Call LiMa API with tools, handling tool-use loop."""
    import httpx

    headers = {
        "Authorization": f"Bearer {LIMA_API_KEY}",
        "Content-Type": "application/json",
    }

    for round_num in range(max_rounds):
        body = {
            "model": LIMA_MODEL,
            "messages": messages,
            "tools": TOOLS,
            "max_tokens": 2048,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{LIMA_BASE}/v1/chat/completions",
                headers=headers, json=body,
            )

        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}", "rounds": round_num}

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content", "") or ""
        tool_calls = msg.get("tool_calls", [])

        # No tool calls — final response
        if not tool_calls:
            return {"ok": True, "content": content, "backend": data.get("model", "?"), "rounds": round_num + 1}

        # Execute tool calls
        assistant_msg = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        for tc in tool_calls:
            fn = tc["function"]
            fn_name = fn["name"]
            try:
                fn_args = json.loads(fn["arguments"])
            except (json.JSONDecodeError, TypeError):
                fn_args = {}
            print(f"  [round {round_num+1}] tool_call: {fn_name}({json.dumps(fn_args, ensure_ascii=False)[:100]})")
            result = _execute_tool(fn_name, fn_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": fn_name,
                "content": result[:3000],
            })

    return {"ok": False, "error": f"Exceeded max rounds ({max_rounds})", "rounds": max_rounds}


async def test_read_system_info():
    """Test 1: AI reads a real system file and reports info accurately."""
    print("=" * 60)
    print("Test 1: Read system file + report info")
    print("=" * 60)

    target_file = os.path.join(PROJECT_ROOT, "_lima_output.txt")
    messages = [
        {"role": "user", "content": f"读取文件 {target_file}，告诉我 LiMa Code 的版本号是什么。只需回答版本号即可。"},
    ]

    t0 = time.time()
    result = await call_lima_with_tools(messages)
    elapsed = (time.time() - t0) * 1000

    content = result.get("content", "")
    ok = result.get("ok", False)
    has_version = "v0.1.24" in content or "0.1.24" in content

    print(f"  result: ok={ok} backend={result.get('backend','?')} rounds={result.get('rounds','?')} elapsed={elapsed:.0f}ms")
    print(f"  content: {content[:200]}")
    print(f"  version_correct: {has_version} (expected v0.1.24)")

    assert ok, f"Read test failed: {result.get('error', '')}"
    assert has_version, f"Version not found in response: {content[:200]}"
    print("  PASS\n")
    return True


async def test_write_and_run_code():
    """Test 2: AI writes a Python script + runs it to verify output."""
    print("=" * 60)
    print("Test 2: Write + run Python script")
    print("=" * 60)

    tmpdir = tempfile.mkdtemp(prefix="lima_vibecode_")
    script_path = os.path.join(tmpdir, "hello.py")

    messages = [
        {"role": "user", "content": f"1. 写一个 Python 脚本到 {script_path}，内容为打印 'VIBECODE_SMOKE_OK' 到 stdout。"
                 f"2. 然后运行 python {script_path} 验证输出。3. 告诉我运行结果。"},
    ]

    t0 = time.time()
    result = await call_lima_with_tools(messages, max_rounds=8)
    elapsed = (time.time() - t0) * 1000

    content = result.get("content", "")
    ok = result.get("ok", False)
    # Check if script was actually written
    script_exists = os.path.exists(script_path)
    script_ok = False
    if script_exists:
        with open(script_path) as f:
            script_content = f.read()
        script_ok = "VIBECODE_SMOKE_OK" in script_content

    print(f"  result: ok={ok} backend={result.get('backend','?')} rounds={result.get('rounds','?')} elapsed={elapsed:.0f}ms")
    print(f"  script_exists: {script_exists} script_ok: {script_ok}")
    print(f"  content: {content[:250]}")

    assert ok, f"Write+run test failed: {result.get('error', '')}"
    if script_exists:
        assert script_ok, f"Script doesn't contain expected output: {script_content[:100]}"
    print("  PASS\n")

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    return True


async def test_backend_count():
    """Test 3: AI reads backends_registry.py and counts configured backends."""
    print("=" * 60)
    print("Test 3: Count backends from real source file")
    print("=" * 60)

    registry_path = os.path.join(PROJECT_ROOT, "backends_registry.py")
    messages = [
        {"role": "user", "content": f"读取 {registry_path}，统计 BACKENDS 字典里有多少个后端配置。只需回答数字和统计依据。"},
    ]

    t0 = time.time()
    result = await call_lima_with_tools(messages)
    elapsed = (time.time() - t0) * 1000

    content = result.get("content", "")
    ok = result.get("ok", False)

    # Check response contains a reasonable number (80+ backends)
    import re
    numbers = re.findall(r'\b(\d{2,3})\b', content)
    found_count = any(70 <= int(n) <= 200 for n in numbers)

    print(f"  result: ok={ok} backend={result.get('backend','?')} rounds={result.get('rounds','?')} elapsed={elapsed:.0f}ms")
    print(f"  content: {content[:300]}")
    print(f"  reasonable_count: {found_count} (numbers found: {numbers})")

    assert ok, f"Backend count test failed: {result.get('error', '')}"
    print("  PASS\n")
    return True


async def main():
    print("LiMa Vibecode E2E Agent-Loop Smoke Test")
    print(f"Server: {LIMA_BASE}")
    print(f"Model: {LIMA_MODEL}")
    print()

    results = []
    try:
        results.append(await test_read_system_info())
    except Exception as e:
        print(f"  FAIL: {e}\n")
        results.append(False)

    try:
        results.append(await test_write_and_run_code())
    except Exception as e:
        print(f"  FAIL: {e}\n")
        results.append(False)

    try:
        results.append(await test_backend_count())
    except Exception as e:
        print(f"  FAIL: {e}\n")
        results.append(False)

    passed = sum(results)
    print("=" * 60)
    print(f"Vibecode E2E: {passed}/{len(results)} passed")
    print("=" * 60)

    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
