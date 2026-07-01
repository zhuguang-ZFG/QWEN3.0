"""Tests for device_gateway.gallery_store."""

from __future__ import annotations

import uuid

import pytest

from device_gateway import gallery_store
from device_logic.db import connect


@pytest.fixture
def account_id() -> str:
    return uuid.uuid4().hex


def _make_account(conn, account_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO v2_account (id, phone, status) VALUES (?, ?, 'active')",
        (account_id, f"phone-{account_id[:8]}"),
    )


@pytest.fixture(autouse=True)
def _clean_gallery_images(tmp_path_factory, monkeypatch: pytest.MonkeyPatch, account_id: str) -> None:
    """Use a temp DB for gallery store tests and clear the table each time."""
    db_path = tmp_path_factory.mktemp("gallery") / "test.db"
    monkeypatch.setenv("LIMA_DB_PATH", str(db_path))
    with connect() as conn:
        _make_account(conn, account_id)
        conn.execute("DELETE FROM v2_gallery_image")
        conn.commit()


def test_add_and_list_image(account_id: str) -> None:
    image = gallery_store.add_image(
        account_id=account_id,
        file_id="telegram-file-1",
        filename="cat.jpg",
        size_bytes=12345,
        mime_type="image/jpeg",
        thumb_url="https://t.me/thumb1",
        tags=["cat", "cute"],
    )
    assert image["id"]
    assert image["fileId"] == "telegram-file-1"
    assert image["tags"] == ["cat", "cute"]

    images = gallery_store.list_images(account_id)
    assert len(images) == 1
    assert images[0]["filename"] == "cat.jpg"


def test_list_images_sorted_and_limited(account_id: str) -> None:
    import time

    for i in range(3):
        gallery_store.add_image(
            account_id=account_id,
            file_id=f"file-{i}",
            filename=f"img{i}.jpg",
            size_bytes=100,
        )
        time.sleep(0.01)
    images = gallery_store.list_images(account_id, limit=2)
    assert len(images) == 2
    # Newest first: file-2 then file-1
    assert images[0]["fileId"] == "file-2"
    assert images[1]["fileId"] == "file-1"


def test_get_image(account_id: str) -> None:
    image = gallery_store.add_image(
        account_id=account_id,
        file_id="telegram-file-get",
        filename="dog.jpg",
        size_bytes=999,
    )
    found = gallery_store.get_image(image["id"], account_id)
    assert found is not None
    assert found["filename"] == "dog.jpg"

    assert gallery_store.get_image("nonexistent", account_id) is None


def test_delete_image(account_id: str) -> None:
    image = gallery_store.add_image(
        account_id=account_id,
        file_id="telegram-file-delete",
        filename="delete.jpg",
        size_bytes=1,
    )
    assert gallery_store.delete_image(image["id"], account_id) is True
    assert gallery_store.get_image(image["id"], account_id) is None
    assert gallery_store.list_images(account_id) == []
    assert gallery_store.delete_image(image["id"], account_id) is False


def test_other_account_cannot_access(account_id: str) -> None:
    other_id = uuid.uuid4().hex
    with connect() as conn:
        _make_account(conn, other_id)
    image = gallery_store.add_image(
        account_id=account_id,
        file_id="telegram-file-private",
        filename="private.jpg",
        size_bytes=1,
    )
    assert gallery_store.get_image(image["id"], other_id) is None
    assert gallery_store.delete_image(image["id"], other_id) is False
    assert gallery_store.list_images(other_id) == []
