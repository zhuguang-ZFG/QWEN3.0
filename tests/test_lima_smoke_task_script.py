import json
import subprocess
import sys


def test_smoke_script_dry_run_outputs_payload():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/create_lima_smoke_task.py",
            "--repo",
            "D:/GIT/lima-worker-sandbox",
            "--kind",
            "review",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    assert data["url_path"] == "/agent/worker/smoke-task"
    assert data["payload"]["repo"] == "D:/GIT/lima-worker-sandbox"
    assert data["payload"]["kind"] == "review"
    assert "api_key" not in proc.stdout.lower()


def test_smoke_script_requires_repo():
    proc = subprocess.run(
        [sys.executable, "scripts/create_lima_smoke_task.py", "--dry-run"],
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "--repo" in proc.stderr
