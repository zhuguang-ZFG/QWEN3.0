import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_agent_task_smoke_script_builds_valid_payloads():
    result = subprocess.run(
        [sys.executable, "scripts/smoke_agent_task_contract.py", "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["task"]["mode"] == "review"
    assert payload["result"]["status"] == "needs_review"
    assert payload["result"]["task_id"] == payload["task"]["task_id"]
