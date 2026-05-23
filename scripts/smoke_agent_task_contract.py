"""Dry-run smoke payload builder for LiMa Server <-> LiMa Code task contract."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_contracts.task_contract import AgentTaskRequest, AgentTaskResult


def build_payload() -> dict:
    task_id = f"smoke-{uuid.uuid4().hex[:8]}"
    task = AgentTaskRequest(
        task_id=task_id,
        repo="D:/GIT/deepcode-cli",
        branch="main",
        goal="Review current diff without modifying files.",
        constraints=["Do not write files", "Return needs_review"],
        allowed_tools=["git_diff"],
        max_runtime_sec=60,
        mode="review",
    )
    task.validate()
    result = AgentTaskResult(
        task_id=task_id,
        status="needs_review",
        summary="Dry-run review payload.",
        changed_files=[],
        test_commands=[],
        test_results=[],
        diff_preview="",
        artifacts=[],
        risks=["dry-run only"],
        next_action="Submit to Server only during manual smoke.",
    )
    result.validate()
    return {"task": asdict(task), "result": asdict(result)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        raise SystemExit("Only --dry-run is supported by this script.")
    print(json.dumps(build_payload(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
