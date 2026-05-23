import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_prompt_recall_module_is_tracked():
    tracked = subprocess.check_output(
        ["git", "ls-files", "session_memory/prompt_recall.py"],
        cwd=ROOT,
        text=True,
    ).splitlines()

    assert tracked == ["session_memory/prompt_recall.py"]
