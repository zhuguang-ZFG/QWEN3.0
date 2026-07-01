"""Tests for AUDIT-6-A1: Swagger/OpenAPI docs disabled by default.

These checks run in isolated subprocesses so that importing ``server`` with
``LIMA_DOCS_ENABLED=1`` does not mutate the app object used by the rest of the
test suite.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_docs_check(env_extra: dict[str, str] | None = None) -> dict[str, dict[str, object]]:
    """Import server in a subprocess and probe the docs endpoints."""
    env = {**os.environ, **(env_extra or {})}
    script = """
import json
from fastapi.testclient import TestClient
import server

client = TestClient(server.app)
result = {}
for path in ("/docs", "/redoc", "/openapi.json"):
    r = client.get(path)
    result[path] = {
        "status": r.status_code,
        "content_type": r.headers.get("content-type", ""),
    }
print(json.dumps(result))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"docs check subprocess failed:\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return json.loads(proc.stdout)


class TestServerDocsDisabled:
    def test_docs_redoc_openapi_disabled_by_default(self):
        data = _run_docs_check()
        for path in ("/docs", "/redoc", "/openapi.json"):
            info = data[path]
            assert info["status"] == 404, f"{path} should be disabled by default, got {info['status']}"

    def test_docs_enabled_via_env_var(self):
        data = _run_docs_check({"LIMA_DOCS_ENABLED": "1"})
        assert data["/docs"]["status"] == 200
        assert "text/html" in data["/docs"]["content_type"]
        assert data["/redoc"]["status"] == 200
        assert data["/openapi.json"]["status"] == 200
