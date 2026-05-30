"""Tests for M8: Sandbox provider interface, fake provider, timeout, cleanup."""
from pathlib import Path
import pytest
from sandbox.provider import (
    SandboxProvider, FakeSandboxProvider,
    SandboxConfig, SandboxFile, SandboxResult,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sandbox"


# ── SandboxConfig ─────────────────────────────────────────────────────────────

def test_config_defaults():
    c = SandboxConfig()
    assert c.image == "python:3.10"
    assert c.timeout_sec == 60.0
    assert c.max_output_chars == 10000


def test_config_custom():
    c = SandboxConfig(timeout_sec=10.0, image="python:3.12")
    assert c.timeout_sec == 10.0


# ── FakeSandboxProvider: lifecycle ────────────────────────────────────────────

def test_create_and_get_id():
    p = FakeSandboxProvider()
    result = p.create()
    assert result.ok is True
    assert result.sandbox_id.startswith("fake-sandbox-")
    assert p.is_alive(result.sandbox_id) is True


def test_terminate_cleans_up():
    p = FakeSandboxProvider()
    r = p.create()
    assert p.terminate(r.sandbox_id) is True
    assert p.is_alive(r.sandbox_id) is False


def test_is_alive_unknown():
    p = FakeSandboxProvider()
    assert p.is_alive("nonexistent") is False


# ── FakeSandboxProvider: file upload ─────────────────────────────────────────

def test_upload_and_run_python_file():
    p = FakeSandboxProvider()
    r = p.create()
    content = (FIXTURE_DIR / "math_utils.py").read_text(encoding="utf-8")

    assert p.upload_files(r.sandbox_id, [
        SandboxFile(path="math_utils.py", content=content),
    ]) is True

    result = p.run_command(r.sandbox_id, "python math_utils.py 3 4")
    assert result.ok is True
    assert "add(3.0, 4.0) = 7.0" in result.stdout
    assert "multiply(3.0, 4.0) = 12.0" in result.stdout

    p.terminate(r.sandbox_id)


def test_upload_unknown_sandbox():
    p = FakeSandboxProvider()
    assert p.upload_files("nonexistent", [SandboxFile(path="x.py", content="")]) is False


# ── FakeSandboxProvider: command execution ────────────────────────────────────

def test_run_command_echo():
    p = FakeSandboxProvider()
    r = p.create()
    result = p.run_command(r.sandbox_id, 'python -c "print(\'hello world\')"')
    assert result.ok is True
    assert "hello world" in result.stdout
    assert result.exit_code == 0
    assert result.duration_ms > 0
    p.terminate(r.sandbox_id)


def test_run_command_exit_code():
    p = FakeSandboxProvider()
    r = p.create()
    result = p.run_command(r.sandbox_id, 'python -c "import sys; sys.exit(2)"')
    assert result.ok is False
    assert result.exit_code == 2
    p.terminate(r.sandbox_id)


def test_run_command_stderr():
    p = FakeSandboxProvider()
    r = p.create()
    result = p.run_command(
        r.sandbox_id,
        'python -c "import sys; print(\'stderr_ok\', file=sys.stderr)"',
    )
    assert result.exit_code == 0
    assert "stderr_ok" in result.stderr
    p.terminate(r.sandbox_id)


def test_run_command_dead_sandbox():
    p = FakeSandboxProvider()
    r = p.create()
    p.terminate(r.sandbox_id)
    result = p.run_command(r.sandbox_id, "echo hi")
    assert result.ok is False
    assert "not alive" in result.error


# ── FakeSandboxProvider: timeout ──────────────────────────────────────────────

def test_run_command_timeout():
    p = FakeSandboxProvider()
    r = p.create(SandboxConfig(timeout_sec=0.5))
    result = p.run_command(r.sandbox_id, 'python -c "import time; time.sleep(10)"')
    assert result.ok is False
    assert "timeout" in result.error.lower()
    p.terminate(r.sandbox_id)


# ── FakeSandboxProvider: output cap ───────────────────────────────────────────

def test_run_command_output_capped():
    p = FakeSandboxProvider()
    r = p.create(SandboxConfig(max_output_chars=50))
    result = p.run_command(r.sandbox_id, "python -c 'print(\"x\" * 200)'")
    assert len(result.stdout) <= 50
    p.terminate(r.sandbox_id)


# ── FakeSandboxProvider: diff collection ──────────────────────────────────────

def test_collect_diff_empty():
    p = FakeSandboxProvider()
    r = p.create()
    p.run_command(r.sandbox_id, "echo test")
    diff = p.collect_diff(r.sandbox_id)
    assert diff == []  # no files created
    p.terminate(r.sandbox_id)


def test_collect_diff_after_file_create():
    p = FakeSandboxProvider()
    r = p.create()
    p.run_command(r.sandbox_id, 'python -c "open(\'output.txt\', \'w\').write(\'content\')"')
    diff = p.collect_diff(r.sandbox_id)
    assert "output.txt" in diff
    p.terminate(r.sandbox_id)


def test_collect_diff_unknown_sandbox():
    p = FakeSandboxProvider()
    assert p.collect_diff("nonexistent") == []


# ── FakeSandboxProvider: no-secret enforcement ────────────────────────────────

def test_fixture_file_has_no_secrets():
    content = (FIXTURE_DIR / "math_utils.py").read_text(encoding="utf-8")
    assert "sk-" not in content
    assert "Bearer" not in content
    assert "password" not in content
    assert "api_key" not in content
    assert "token" not in content.lower()


def test_sandbox_result_no_secret_fields():
    r = SandboxResult(ok=True, exit_code=0, stdout="hello", stderr="")
    d = {k: v for k, v in r.__dict__.items()}
    assert "api_key" not in d
    assert "token" not in d


# ── FakeSandboxProvider: provider is abstract ─────────────────────────────────

def test_sandbox_provider_is_abstract():
    with pytest.raises(TypeError):
        SandboxProvider()


# ── FakeSandboxProvider: multiple sandboxes concurrently ──────────────────────

def test_multiple_sandboxes_independent():
    p = FakeSandboxProvider()
    r1 = p.create()
    r2 = p.create()

    p.upload_files(r1.sandbox_id, [SandboxFile(path="a.txt", content="alpha")])
    p.upload_files(r2.sandbox_id, [SandboxFile(path="b.txt", content="beta")])

    result1 = p.run_command(r1.sandbox_id, 'python -c "print(open(\'a.txt\').read())"')
    result2 = p.run_command(r2.sandbox_id, 'python -c "print(open(\'b.txt\').read())"')

    assert "alpha" in result1.stdout
    assert "beta" in result2.stdout
    # Isolation: r1 should not have b.txt
    r1_check = p.run_command(
        r1.sandbox_id,
        'python -c "import pathlib, sys; sys.exit(0 if pathlib.Path(\'b.txt\').exists() else 2)"',
    )
    assert r1_check.ok is False

    p.terminate(r1.sandbox_id)
    p.terminate(r2.sandbox_id)


# ── FakeSandboxProvider: terminate is idempotent ──────────────────────────────

def test_terminate_idempotent():
    p = FakeSandboxProvider()
    r = p.create()
    assert p.terminate(r.sandbox_id) is True
    assert p.terminate(r.sandbox_id) is True  # second call fine


def test_upload_rejects_path_escape():
    p = FakeSandboxProvider()
    r = p.create()
    assert p.upload_files(
        r.sandbox_id, [SandboxFile(path="../escape.txt", content="nope")]
    ) is False
    p.terminate(r.sandbox_id)


def test_host_secret_env_not_leaked(monkeypatch):
    monkeypatch.setenv("LIMA_SECRET_TOKEN", "host-secret-value")
    p = FakeSandboxProvider()
    r = p.create()
    result = p.run_command(
        r.sandbox_id,
        'python -c "import os; print(os.environ.get(\'LIMA_SECRET_TOKEN\', \'\'))"',
    )
    assert result.ok is True
    assert "host-secret-value" not in result.stdout
    p.terminate(r.sandbox_id)
