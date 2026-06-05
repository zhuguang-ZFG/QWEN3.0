#!/usr/bin/env python3
"""Real OpenCode + LiMa integration verification (uses local opencode CLI + user config).

Reads API key from ~/.config/opencode/opencode.json (lima provider).
Runs opencode CLI scenarios against https://chat.donglicao.com and reports results.

Usage:
    python scripts/opencode_real_verify.py
    python scripts/opencode_real_verify.py --scenario ping
    python scripts/opencode_real_verify.py --scenario coding --timeout 300
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://chat.donglicao.com"
OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    latency_ms: int = 0
    output_snippet: str = ""
    error: str = ""


@dataclass
class IntegrationReport:
    timestamp: str = ""
    opencode_version: str = ""
    lima_base: str = ""
    results: list = field(default_factory=list)

    @property
    def summary(self) -> dict:
        passed = sum(1 for r in self.results if r["passed"])
        return {
            "total": len(self.results),
            "passed": passed,
            "failed": len(self.results) - passed,
            "all_passed": passed == len(self.results),
        }


def _load_lima_api_key() -> str:
    env_key = os.environ.get("LIMA_API_KEY", "").strip()
    if env_key:
        return env_key
    if not OPENCODE_CONFIG.is_file():
        sys.exit(f"ERROR: missing {OPENCODE_CONFIG} and LIMA_API_KEY")
    data = json.loads(OPENCODE_CONFIG.read_text(encoding="utf-8"))
    provider = data.get("provider", {}).get("lima", {})
    key = provider.get("options", {}).get("apiKey", "")
    if not key:
        sys.exit("ERROR: lima apiKey not found in opencode.json")
    return key


def _opencode_bin() -> str:
    import shutil

    for name in ("opencode.cmd", "opencode"):
        path = shutil.which(name)
        if path:
            return path
    npm = Path(os.environ.get("APPDATA", "")) / "npm" / "opencode.cmd"
    if npm.is_file():
        return str(npm)
    return "opencode"


def _opencode_version() -> str:
    try:
        out = subprocess.check_output(
            [_opencode_bin(), "--version"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
        return out.strip().splitlines()[-1]
    except Exception as exc:
        return f"unknown ({type(exc).__name__})"


def _run_opencode(
    prompt: str,
    *,
    model: str = "lima/lima-1.3",
    timeout: int = 300,
    work_dir: Path | None = None,
) -> tuple[bool, str, str]:
    """Run opencode CLI; return (ok, stdout, stderr)."""
    api_key = _load_lima_api_key()
    env = os.environ.copy()
    env["LIMA_API_KEY"] = api_key

    with tempfile.TemporaryDirectory(prefix="opencode-lima-") as tmp:
        cwd = str(work_dir or Path(tmp))
        cmd = [
            _opencode_bin(),
            "run",
            "--pure",
            "--dangerously-skip-permissions",
            "-m",
            model,
            "--dir",
            cwd,
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            return False, "", f"timeout after {timeout}s"
        except FileNotFoundError:
            return False, "", "opencode CLI not found in PATH"

    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return False, proc.stdout or "", proc.stderr or f"exit {proc.returncode}"
    return True, proc.stdout or "", proc.stderr or ""


def _api_chat(
    messages: list[dict],
    *,
    stream: bool = False,
    tools: list | None = None,
    timeout: float = 120,
) -> tuple[bool, dict]:
    """Direct HTTP to LiMa mimicking OpenCode client headers."""
    import httpx

    api_key = _load_lima_api_key()
    base = os.environ.get("LIMA_SERVER_URL", DEFAULT_BASE).rstrip("/")
    body: dict = {
        "model": "lima-1.3",
        "messages": messages,
        "max_tokens": 512,
        "stream": stream,
    }
    if tools:
        body["tools"] = tools

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "OpenCode/1.0",
    }
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            if not stream:
                resp = client.post(f"{base}/v1/chat/completions", headers=headers, json=body)
                ms = int((time.perf_counter() - t0) * 1000)
                if resp.status_code != 200:
                    return False, {"latency_ms": ms, "error": resp.text[:300]}
                data = resp.json()
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                return True, {
                    "latency_ms": ms,
                    "content": msg.get("content", ""),
                    "tool_calls": msg.get("tool_calls", []),
                    "model": data.get("model", ""),
                }
            # streaming minimal check
            content_parts: list[str] = []
            with client.stream(
                "POST", f"{base}/v1/chat/completions", headers=headers, json=body
            ) as resp:
                if resp.status_code != 200:
                    ms = int((time.perf_counter() - t0) * 1000)
                    return False, {"latency_ms": ms, "error": resp.read()[:300]}
                for line in resp.iter_lines():
                    if line.startswith("data: ") and line[6:].strip() != "[DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if delta.get("content"):
                                content_parts.append(delta["content"])
                        except json.JSONDecodeError:
                            pass
            ms = int((time.perf_counter() - t0) * 1000)
            return bool(content_parts), {
                "latency_ms": ms,
                "content": "".join(content_parts),
            }
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        return False, {"latency_ms": ms, "error": f"{type(exc).__name__}: {exc}"}


def scenario_ping() -> ScenarioResult:
    t0 = time.perf_counter()
    ok, out, err = _run_opencode(
        "Reply with exactly one line: OPENCODE_LIMA_PING_OK",
        timeout=360,
    )
    ms = int((time.perf_counter() - t0) * 1000)
    snippet = (out or err)[-500:]
    passed = ok and "OPENCODE_LIMA_PING_OK" in (out or "").upper().replace(" ", "_")
    return ScenarioResult(
        name="opencode_cli_ping",
        passed=passed,
        latency_ms=ms,
        output_snippet=snippet,
        error="" if passed else (err or snippet)[:200],
    )


def scenario_api_coding() -> ScenarioResult:
    messages = [
        {"role": "system", "content": "You are OpenCode, an AI coding assistant."},
        {
            "role": "user",
            "content": "Write a Python one-liner that reverses a string. Code only.",
        },
    ]
    ok, data = _api_chat(messages)
    content = data.get("content", "")
    passed = ok and ("[::-1]" in content or "reversed" in content.lower())
    return ScenarioResult(
        name="api_coding_opencode_path",
        passed=passed,
        latency_ms=data.get("latency_ms", 0),
        output_snippet=content[:300],
        error=data.get("error", ""),
    )


def scenario_api_tool() -> ScenarioResult:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }
    ]
    messages = _opencode_messages("Read the file routing_engine.py and summarize in 1 sentence.")
    ok, data = _api_chat(messages, tools=tools, stream=True, timeout=240)
    passed = ok and len(data.get("content", "")) > 10
    return ScenarioResult(
        name="api_stream_coding_opencode",
        passed=passed,
        latency_ms=data.get("latency_ms", 0),
        output_snippet=data.get("content", "")[:300],
        error=data.get("error", ""),
    )


def _opencode_messages(user_content: str) -> list[dict]:
    return [
        {"role": "system", "content": "You are OpenCode, an AI coding assistant."},
        {"role": "user", "content": user_content},
    ]


def scenario_models() -> ScenarioResult:
    t0 = time.perf_counter()
    try:
        out = subprocess.check_output(
            [_opencode_bin(), "models", "lima"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
            env={**os.environ, "LIMA_API_KEY": _load_lima_api_key()},
        )
        ms = int((time.perf_counter() - t0) * 1000)
        models = [ln.strip() for ln in out.splitlines() if ln.strip()]
        passed = "lima/lima-1.3" in models
        return ScenarioResult(
            name="opencode_models_lima",
            passed=passed,
            latency_ms=ms,
            output_snippet=", ".join(models[:6]),
            error="" if passed else "lima-1.3 missing",
        )
    except Exception as exc:
        return ScenarioResult(
            name="opencode_models_lima",
            passed=False,
            error=str(exc),
        )


SCENARIOS = {
    "models": scenario_models,
    "ping": scenario_ping,
    "coding": scenario_api_coding,
    "stream": scenario_api_tool,
    "all": None,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Real OpenCode + LiMa integration verify")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="all",
    )
    parser.add_argument("--json-report", default=str(PROJECT_ROOT / "data" / "opencode_real_verify.json"))
    args = parser.parse_args()

    os.environ.setdefault("LIMA_API_KEY", _load_lima_api_key())

    names = (
        ["models", "coding", "stream", "ping"]
        if args.scenario == "all"
        else [args.scenario]
    )

    results: list[ScenarioResult] = []
    print(f"OpenCode real integration — LiMa @ {DEFAULT_BASE}")
    print(f"OpenCode version: {_opencode_version()}")
    print()

    for name in names:
        fn = SCENARIOS[name]
        assert fn is not None
        print(f"[.] {name} ...", flush=True)
        r = fn()
        results.append(r)
        status = "PASS" if r.passed else "FAIL"
        print(f"    {status} {r.latency_ms}ms — {r.name}")
        if r.output_snippet:
            print(f"    snippet: {r.output_snippet[:120]}")
        if r.error:
            print(f"    error: {r.error[:120]}")

    report = IntegrationReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        opencode_version=_opencode_version(),
        lima_base=DEFAULT_BASE,
        results=[asdict(r) for r in results],
    )
    Path(args.json_report).write_text(
        json.dumps({**asdict(report), "summary": report.summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    s = report.summary
    print(f"Summary: {s['passed']}/{s['total']} passed")
    print(f"Report: {args.json_report}")
    sys.exit(0 if s["all_passed"] else 1)


if __name__ == "__main__":
    main()
