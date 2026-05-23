import json
import subprocess
import sys


def test_agent_task_smoke_script_builds_valid_payloads():
    result = subprocess.run(
        [sys.executable, "scripts/smoke_agent_task_contract.py", "--dry-run"],
        cwd="D:/GIT",
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["task"]["mode"] == "review"
    assert payload["result"]["status"] == "needs_review"
    assert payload["result"]["task_id"] == payload["task"]["task_id"]
