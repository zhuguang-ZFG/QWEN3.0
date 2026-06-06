#!/usr/bin/env python3
"""Sandbox probes for no-login web AI candidates."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "free_web_ai_candidates.json"
DEFAULT_OUTPUT = ROOT / "data" / "free_web_ai_probe_results.json"
PROBE_PROMPT = "Say OK only."


def normalize_error(status_code: int | None, text: str) -> str:
    """Map provider-specific failures to stable LiMa classes."""
    lowered = text.lower()
    if "anonymous_usage_exceeded" in lowered:
        return "manual_refresh_required"
    if status_code in {401, 403} or any(
        marker in lowered for marker in ("unauthorized", "forbidden", "invalid token")
    ):
        return "auth_expired"
    if status_code == 429 or any(
        marker in lowered for marker in ("too many requests", "rate limit")
    ):
        return "rate_limited"
    if any(marker in lowered for marker in ("quota", "usage exhausted", "limit exceeded")):
        return "quota_exhausted"
    if any(marker in lowered for marker in ("timeout", "timed out")):
        return "timeout"
    if any(
        marker in lowered
        for marker in ("captcha", "cloudflare challenge", "access denied", "blocked")
    ):
        return "blocked"
    if status_code is not None and 500 <= status_code <= 599:
        return "provider_error"
    if status_code is not None and 200 <= status_code <= 299:
        return "ok"
    return "unknown_error"


def load_candidates(path: str | Path) -> list[dict[str, Any]]:
    registry_path = Path(path)
    candidates = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(candidates, list):
        raise ValueError("candidate registry must be a JSON list")
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("candidate registry entries must be objects")
        for key in ("id", "url", "trust", "enabled", "private_code_allowed"):
            if key not in item:
                raise ValueError(f"candidate missing required key: {key}")
    return candidates


def write_results(path: str | Path, results: list[dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def probe_candidate(candidate: dict[str, Any], timeout: float) -> dict[str, Any]:
    start = time.perf_counter()
    request = urllib.request.Request(
        candidate["url"],
        headers={"User-Agent": "LiMa-free-web-ai-probe/0.1"},
        method="GET",
    )
    status_code: int | None = None
    body_preview = ""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.getcode()
            body_preview = response.read(512).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        body_preview = exc.read(512).decode("utf-8", errors="replace")
    except TimeoutError as exc:
        body_preview = str(exc) or "timeout"
    except urllib.error.URLError as exc:
        body_preview = str(exc.reason)

    latency_ms = int((time.perf_counter() - start) * 1000)
    status = normalize_error(status_code, body_preview)
    return {
        "id": candidate["id"],
        "url": candidate["url"],
        "status": status,
        "http_status": status_code,
        "latency_ms": latency_ms,
        "private_code_allowed": bool(candidate.get("private_code_allowed", False)),
        "probe_prompt": PROBE_PROMPT,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidates = load_candidates(args.registry)
    if args.max_candidates:
        candidates = candidates[: args.max_candidates]

    print(f"Candidates ({len(candidates)}): {', '.join(c['id'] for c in candidates)}")
    if args.dry_run:
        return 0

    results = [probe_candidate(candidate, args.timeout) for candidate in candidates]
    write_results(args.out, results)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
