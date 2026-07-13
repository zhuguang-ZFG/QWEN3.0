"""Tests for fix P1: captcha answers stored as SHA-256 hash instead of plaintext."""

from __future__ import annotations

import hashlib

from device_logic.captcha import create_captcha, verify_captcha
from device_logic.db import connect


def test_create_captcha_stores_hash_not_plaintext(tmp_path, monkeypatch) -> None:
    """DB 中 code 列存的是 SHA-256 哈希，不是明文."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("LIMA_DB_PATH", str(db_path))
    captcha_id, code = create_captcha("TEST1")
    with connect() as conn:
        row = conn.execute("SELECT code FROM v2_captcha WHERE id=?", (captcha_id,)).fetchone()
    assert row is not None
    stored = row["code"]
    expected_hash = hashlib.sha256(b"TEST1").hexdigest()
    assert stored == expected_hash, f"expected hash {expected_hash}, got {stored}"
    assert stored != "TEST1", "plaintext must not be stored"


def test_verify_captcha_correct_answer_passes(tmp_path, monkeypatch) -> None:
    """正确验证码验证通过（返回 None）."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("LIMA_DB_PATH", str(db_path))
    captcha_id, code = create_captcha("ABCD")
    result = verify_captcha(captcha_id, code)
    assert result is None, "correct answer should succeed"


def test_verify_captcha_wrong_answer_rejected(tmp_path, monkeypatch) -> None:
    """错误验证码被拒绝（返回错误响应）."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("LIMA_DB_PATH", str(db_path))
    captcha_id, code = create_captcha("ABCD")
    result = verify_captcha(captcha_id, "wrong")
    assert result is not None, "wrong answer should return error"
    assert result.status_code == 400
