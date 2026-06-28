"""Temporary git credential store for Gitee tokens."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def gitee_credential_store(token: str, repo: str | Path = "") -> Iterator[Path]:
    """Yield a temporary git credential-store file containing the Gitee token.

    The file is created inside the repository's ``.git`` directory so git can
    acquire its storage lock without cross-directory permission issues. It is
    created with mode 0600 (on Unix) and deleted when the context exits.
    """
    repo_path = Path(repo) if repo else Path.cwd()
    git_dir = repo_path / ".git"
    if not git_dir.is_dir():
        git_dir = repo_path
    fd, path_str = tempfile.mkstemp(prefix="gitee_cred_", dir=git_dir, text=True)
    path = Path(path_str)
    try:
        os.write(fd, f"https://oauth2:{token}@gitee.com\n".encode())
        os.close(fd)
        os.chmod(path, 0o600)
        yield path
    finally:
        path.unlink(missing_ok=True)
