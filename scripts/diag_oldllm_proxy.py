#!/usr/bin/env python3
"""CLI wrapper for TheOldLLM upstream/local proxy diagnosis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oldllm_diag import DEFAULT_CHAT_TIMEOUT, DEFAULT_LOCAL_PROXY, DEFAULT_UPSTREAM, run_diag


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upstream",
        default=DEFAULT_UPSTREAM,
        help="Direct TheOldLLM base URL",
    )
    parser.add_argument(
        "--local-proxy",
        default=DEFAULT_LOCAL_PROXY,
        help="Local proxy base URL (e.g. http://127.0.0.1:4502)",
    )
    parser.add_argument(
        "--chat-timeout",
        type=float,
        default=DEFAULT_CHAT_TIMEOUT,
        help="Chat probe timeout seconds",
    )
    parser.add_argument(
        "--models-only",
        action="store_true",
        help="Skip chat completion probes",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON only",
    )
    args = parser.parse_args()

    report = run_diag(
        upstream=args.upstream.rstrip("/"),
        local_proxy=args.local_proxy.rstrip("/"),
        chat_timeout=args.chat_timeout,
        skip_chat=args.models_only,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("TheOldLLM diagnosis")
        print(f"  upstream:    {report['upstream']}")
        print(f"  local_proxy: {report['local_proxy']}")
        for item in report["results"]:
            label = item.get("label", "?")
            kind = item.get("kind", "?")
            status = item.get("status")
            elapsed = item.get("elapsed_sec")
            ok = item.get("ok")
            mark = "ok" if ok else "FAIL"
            extra = ""
            if kind == "models":
                extra = f" models={item.get('model_count', 0)}"
            elif kind == "chat":
                extra = f" model={item.get('model')}"
                if item.get("timed_out"):
                    extra += " timed_out"
            print(
                f"  [{mark}] {label}/{kind} status={status} "
                f"elapsed={elapsed}s{extra}"
            )
        print(
            f"  summary: models_ok={report['any_models_ok']} "
            f"chat_ok={report['any_chat_ok']}"
        )

    if report["any_chat_ok"]:
        return 0
    if report["any_models_ok"]:
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
