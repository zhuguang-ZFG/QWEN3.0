"""Tests for client_keys storage layer."""

from __future__ import annotations


import pytest

from client_keys.storage import ClientKeyStorage, ClientKeyStorageError, _mask_key


@pytest.fixture
def storage(tmp_path):
    return ClientKeyStorage(str(tmp_path / "client_keys.db"))


def test_create_key(storage):
    key = storage.create("cursor-user", quota_daily=500)
    assert key.key_id.startswith("ck-")
    assert key.key_value.startswith("lima-")
    assert key.label == "cursor-user"
    assert key.quota_daily == 500
    assert key.enabled is True


def test_key_id_does_not_contain_raw_key_suffix(storage):
    key = storage.create("test")
    assert key.key_value[-4:] not in key.key_id


def test_mask_key_long_value():
    value = "lima-abcdef01-23456789-abcd1234"
    masked = _mask_key(value)
    assert masked.startswith("lima-abcde")
    assert masked.endswith("1234")
    assert "****" in masked


def test_mask_key_empty_value():
    assert _mask_key("") == ""


def test_list_all(storage):
    storage.create("a")
    storage.create("b")
    keys = storage.list_all()
    assert len(keys) == 2
    assert keys[0].created_at >= keys[1].created_at


def test_get_by_key_id(storage):
    created = storage.create("find-me")
    found = storage.get_by_key_id(created.key_id)
    assert found is not None
    assert found.label == "find-me"


def test_get_by_key_id_not_found(storage):
    assert storage.get_by_key_id("ck-nonexistent") is None


def test_get_by_value(storage):
    created = storage.create("by-value")
    found = storage.get_by_value(created.key_value)
    assert found is not None
    assert found.key_id == created.key_id


def test_get_by_value_not_found(storage):
    assert storage.get_by_value("lima-not-real") is None


def test_update(storage):
    created = storage.create("update-me")
    ok = storage.update(created.key_id, {"label": "updated", "enabled": False})
    assert ok is True
    updated = storage.get_by_key_id(created.key_id)
    assert updated.label == "updated"
    assert updated.enabled is False


def test_update_allowed_urls(storage):
    created = storage.create("url-test")
    storage.update(created.key_id, {"allowed_urls": ["/v1/models"]})
    updated = storage.get_by_key_id(created.key_id)
    assert updated.allowed_urls == ["/v1/models"]


def test_update_not_found(storage):
    assert storage.update("ck-missing", {"label": "x"}) is False


def test_delete(storage):
    created = storage.create("delete-me")
    assert storage.delete(created.key_id) is True
    assert storage.get_by_key_id(created.key_id) is None


def test_delete_not_found(storage):
    assert storage.delete("ck-missing") is False


def test_regenerate_preserves_key_id(storage):
    created = storage.create("regen-me")
    original_id = created.key_id
    regenerated = storage.regenerate(original_id)
    assert regenerated is not None
    assert regenerated.key_id == original_id
    assert regenerated.key_value != created.key_value


def test_regenerate_not_found(storage):
    assert storage.regenerate("ck-missing") is None


def test_storage_logs_errors_on_bad_db_path(tmp_path, caplog):
    # Use an existing file as the parent "directory" to force mkdir to fail.
    bad_parent = tmp_path / "file_not_dir"
    bad_parent.write_text("x", encoding="utf-8")
    bad_path = str(bad_parent / "keys.db")
    with pytest.raises(ClientKeyStorageError):
        ClientKeyStorage(bad_path)
    assert any("client_keys" in r.message for r in caplog.records)


def test_storage_error_on_corrupt_db(tmp_path, caplog):
    db_path = tmp_path / "corrupt.db"
    db_path.write_bytes(b"not sqlite")
    with pytest.raises(ClientKeyStorageError):
        ClientKeyStorage(str(db_path))
    assert any("client_keys" in r.message for r in caplog.records)
