"""Temporary git credential store for Gitee tokens."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def gitee_credential_store(token: str) -> Iterator[Path]:
    """Yield a temporary git credential-store file containing the Gitee token.

    The file is created with mode 0600 and deleted when the context exits.
    """
    fd, path_str = tempfile.mkstemp(prefix="gitee_cred_", text=True)
    path = Path(path_str)
    try:
        os.write(fd, f"https://oauth2:{token}@gitee.com\n".encode())
        os.close(fd)
        os.chmod(path, 0o600)
        yield path
    finally:
        path.unlink(missing_ok=True)
