#!/usr/bin/env python3
"""
Push refreshed API keys to LiMa VPS.

Usage:
  python push_tokens.py --token <LIMA_API_KEY>
  python push_tokens.py --env  (reads from .env file)

Scans D:\ollama_server\ for refresh scripts, extracts latest tokens,
and pushes them to the VPS token-sync endpoint.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

VPS_URL = "http://47.112.162.80:8080"
TOKEN_SYNC_URL = f"{VPS_URL}/internal/v1/token-sync"
TOKEN_STATUS_URL = f"{VPS_URL}/internal/v1/token-sync/status"

# Known token sources (Windows paths)
TOKEN_SOURCES = {
    "longcat": {
        "env_file": r"D:\ollama_server\.env",
        "env_var": "LONGCAT_API_KEY",
        "url": "https://api.longcat.chat/anthropic/v1/messages",
        "model": "LongCat-2.0-Preview",
        "format": "anthropic",
    },
    "mimo_v2_5": {
        "env_file": r"D:\ollama_server\.env",
        "env_var": "MIMO_API_KEY",
        "url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        "model": None,  # use backends.py default
        "format": "openai",
    },
    "ms_kimi_k25": {
        "env_file": r"D:\ollama_server\.env",
        "env_var": "MODELSCOPE_API_KEY",
        "url": "https://api-inference.modelscope.cn/v1/chat/completions",
        "model": "moonshotai/Kimi-K2.5",
        "format": "openai",
    },
}


def load_tokens_from_env() -> dict[str, str]:
    """Load tokens from .env files."""
    tokens = {}
    for name, src in TOKEN_SOURCES.items():
        env_file = src["env_file"]
        env_var = src["env_var"]
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{env_var}="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if key and key != "none":
                            tokens[name] = key
                            break
    return tokens


def push_tokens(tokens: dict[str, str], api_key: str) -> dict:
    """Push tokens to VPS token-sync endpoint."""
    body = json.dumps({"tokens": tokens}).encode()
    req = urllib.request.Request(
        TOKEN_SYNC_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:200]
        except:
            pass
        return {"error": f"HTTP {e.code}", "body": body_text}
    except Exception as e:
        return {"error": str(e)}


def check_status(api_key: str) -> dict:
    """Check token sync status on VPS."""
    req = urllib.request.Request(
        TOKEN_STATUS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Push refreshed tokens to LiMa VPS")
    parser.add_argument("--token", help="LiMa API key for auth")
    parser.add_argument("--env", action="store_true", help="Read token from .env")
    parser.add_argument("--status", action="store_true", help="Check status only")
    parser.add_argument("--dry-run", action="store_true", help="Show tokens without pushing")
    args = parser.parse_args()

    # Resolve API key
    api_key = args.token or ""
    if not api_key and args.env:
        api_key = os.environ.get("LIMA_API_KEY", "")
    if not api_key:
        api_key = os.environ.get("LIMA_API_KEY", "")
    if not api_key:
        print("Error: --token <key> or LIMA_API_KEY env var required")
        sys.exit(1)

    if args.status:
        print("Checking VPS token sync status...")
        result = check_status(api_key)
        print(json.dumps(result, indent=2))
        return

    # Load tokens
    tokens = load_tokens_from_env()
    print(f"Loaded {len(tokens)} tokens:")
    for name, key in tokens.items():
        print(f"  {name}: {key[:15]}...")

    if not tokens:
        print("No tokens found. Check .env files at D:\\ollama_server\\")
        sys.exit(1)

    if args.dry_run:
        print("\nDry run — not pushing")
        return

    # Push to VPS
    print(f"\nPushing to {TOKEN_SYNC_URL}...")
    result = push_tokens(tokens, api_key)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
