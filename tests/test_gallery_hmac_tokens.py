"""Unit tests for gallery HMAC token purpose scoping."""

from __future__ import annotations

import pytest

from device_gateway.gallery_service import (
    GALLERY_TOKEN_PURPOSE_FILE,
    GALLERY_TOKEN_PURPOSE_THUMB,
    issue_gallery_fetch_token,
    issue_gallery_thumb_token,
    parse_gallery_hmac_token,
)


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")


def test_thumb_and_file_tokens_have_distinct_purposes() -> None:
    thumb = issue_gallery_thumb_token("owner", "img-1")
    file_token = issue_gallery_fetch_token("owner", "img-1")
    assert thumb and file_token

    thumb_parsed = parse_gallery_hmac_token(thumb)
    file_parsed = parse_gallery_hmac_token(file_token)
    assert thumb_parsed == ("owner", "img-1", GALLERY_TOKEN_PURPOSE_THUMB)
    assert file_parsed == ("owner", "img-1", GALLERY_TOKEN_PURPOSE_FILE)


def test_file_token_rejected_when_parsed_as_thumb_only() -> None:
    file_token = issue_gallery_fetch_token("owner", "img-2")
    assert file_token
    parsed = parse_gallery_hmac_token(file_token)
    assert parsed is not None
    assert parsed[2] == GALLERY_TOKEN_PURPOSE_FILE
