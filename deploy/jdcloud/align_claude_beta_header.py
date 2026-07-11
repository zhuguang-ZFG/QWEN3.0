#!/usr/bin/env python3
"""Align Claude anthropic-beta to 2024-07-31 (match :3001 proxy)."""

import json
import subprocess

HEADER = json.dumps({"anthropic-beta": "prompt-caching-2024-07-31"})
MODELS = json.dumps(
    {
        "claude-opus-4-8": {"anthropic-beta": "prompt-caching-2024-07-31"},
        "claude-opus-4-7": {"anthropic-beta": "prompt-caching-2024-07-31"},
        "claude-opus-4-6": {"anthropic-beta": "prompt-caching-2024-07-31"},
    }
)


def mysql_exec(sql: str) -> None:
    subprocess.check_call(["mysql", "--default-character-set=utf8mb4", "-e", sql])


def main() -> None:
    # escape single quotes for SQL string literals
    h = HEADER.replace("\\", "\\\\").replace("'", "''")
    m = MODELS.replace("\\", "\\\\").replace("'", "''")
    mysql_exec(f"UPDATE newapi.channels SET header_override='{h}' WHERE id=13;")
    mysql_exec(
        "INSERT INTO newapi.options(`key`,value) VALUES("
        f"'claude.model_headers_settings','{m}') "
        "ON DUPLICATE KEY UPDATE value=VALUES(value);"
    )
    print(
        "header",
        subprocess.check_output(
            ["mysql", "-N", "-e", "SELECT header_override FROM newapi.channels WHERE id=13"],
            text=True,
        ).strip(),
    )
    subprocess.check_call("cd /opt/newapi && docker-compose restart new-api", shell=True)
    print("OK")


if __name__ == "__main__":
    main()
