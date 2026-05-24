from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

RUNTIME_FILES = [
    ROOT / "backends.py",
    ROOT / "fc_caller.py",
    ROOT / "mimo_tts.py",
    ROOT / "server.py",
    ROOT / "http_caller.py",
    ROOT / "tool_dispatcher.py",
] + sorted((ROOT / "lima_fc_tools").glob("*.py"))


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]"),
    re.compile(r"(?i)(api_key|apikey|secret|token)\s*=\s*['\"][^'\"]{8,}['\"]"),
]


def test_runtime_files_do_not_contain_hardcoded_secret_literals():
    offenders = []
    for path in RUNTIME_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(path.name)
                break

    assert offenders == []
