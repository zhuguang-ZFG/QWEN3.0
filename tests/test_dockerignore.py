from pathlib import Path


def test_root_dockerignore_excludes_local_secrets_and_state():
    text = Path(".dockerignore").read_text(encoding="utf-8")

    for pattern in (".env", ".env.*", ".git/", ".lima-data/", "data/", ".codex/", ".claude/"):
        assert pattern in text
