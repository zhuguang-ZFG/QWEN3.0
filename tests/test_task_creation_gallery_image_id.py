"""Tests for gallery_image_id in draw_generated task params."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from device_gateway.tasks import project_to_motion_task_async, reset_tasks_for_tests


@pytest.fixture(autouse=True)
def _reset_store():
    reset_tasks_for_tests()
    yield
    reset_tasks_for_tests()


@pytest.mark.asyncio
async def test_draw_generated_gallery_image_id_resolves_without_persisting_url(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "gallery_draw.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_VERIFY_HOST", "chat.donglicao.com")

    from device_logic.db import _schema_ready_paths, connect
    from device_gateway import gallery_store

    _schema_ready_paths.clear()
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
            ("owner", "owner-phone", "owner"),
        )
        conn.commit()

    image = gallery_store.add_image(
        account_id="owner",
        file_id="telegram-file-id",
        filename="cat.jpg",
        size_bytes=1234,
        mime_type="image/jpeg",
        thumb_url="https://api.telegram.org/file/botsecret/thumb.jpg",
        tags=[],
    )

    voice_task = {
        "capability": "draw_generated",
        "params": {
            "prompt": "",
            "gallery_image_id": image["id"],
            "_account_id": "owner",
        },
        "source": "api",
    }
    mock_draw = AsyncMock(
        return_value={
            "status": "success",
            "image_url": "https://chat.donglicao.com/device/v1/app/gallery/x/file?fetch_token=secret",
            "svg_path": "M 10 10 L 50 50 L 90 10 Z",
            "width": 180,
            "height": 180,
            "model": "wanx2.1-t2i-turbo",
            "error": None,
        }
    )
    with patch("device_gateway.task_draw_params.handle_device_draw", mock_draw):
        task = await project_to_motion_task_async("dev-gallery-1", voice_task)

    assert "error" not in task
    mock_draw.assert_awaited_once()
    call_kwargs = mock_draw.await_args.kwargs
    assert call_kwargs["image_url"].startswith("https://chat.donglicao.com/device/v1/app/gallery/")
    assert "fetch_token=" in call_kwargs["image_url"]

    params = task["params"]
    assert params["gallery_image_id"] == image["id"]
    assert "image_url" not in params
    assert params["prompt"].startswith("gallery:")


@pytest.mark.asyncio
async def test_draw_generated_gallery_image_id_requires_account_context():
    voice_task = {
        "capability": "draw_generated",
        "params": {
            "prompt": "",
            "gallery_image_id": "img-1",
        },
        "source": "api",
    }
    task = await project_to_motion_task_async("dev-gallery-3", voice_task)
    assert task.get("error", {}).get("code") == "draw_failed"
    assert "account context" in str(task.get("error", {}).get("reason", "")).lower()


@pytest.mark.asyncio
async def test_draw_generated_gallery_image_id_ignores_image_url(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "gallery_draw_priority.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_VERIFY_HOST", "chat.donglicao.com")

    from device_logic.db import _schema_ready_paths, connect
    from device_gateway import gallery_store

    _schema_ready_paths.clear()
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
            ("owner", "owner-phone", "owner"),
        )
        conn.commit()

    image = gallery_store.add_image(
        account_id="owner",
        file_id="telegram-file-id",
        filename="cat.jpg",
        size_bytes=1234,
        mime_type="image/jpeg",
        thumb_url="https://api.telegram.org/file/botsecret/thumb.jpg",
        tags=[],
    )

    voice_task = {
        "capability": "draw_generated",
        "params": {
            "prompt": "",
            "gallery_image_id": image["id"],
            "_account_id": "owner",
            "image_url": "https://api.telegram.org/file/botsecret/evil.jpg",
        },
        "source": "api",
    }
    mock_draw = AsyncMock(
        return_value={
            "status": "success",
            "svg_path": "M 10 10 L 50 50 L 90 10 Z",
            "width": 180,
            "height": 180,
            "model": "wanx2.1-t2i-turbo",
            "error": None,
        }
    )
    with patch("device_gateway.task_draw_params.handle_device_draw", mock_draw):
        task = await project_to_motion_task_async("dev-gallery-4", voice_task)

    assert "error" not in task
    call_kwargs = mock_draw.await_args.kwargs
    assert call_kwargs["image_url"].startswith("https://chat.donglicao.com/device/v1/app/gallery/")
    assert "api.telegram.org/file/botsecret/evil.jpg" not in call_kwargs["image_url"]


@pytest.mark.asyncio
async def test_draw_generated_gallery_image_id_rejects_unsupported_mime(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "gallery_draw_mime.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")

    from device_logic.db import _schema_ready_paths, connect
    from device_gateway import gallery_store

    _schema_ready_paths.clear()
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
            ("owner", "owner-phone", "owner"),
        )
        conn.commit()

    image = gallery_store.add_image(
        account_id="owner",
        file_id="telegram-file-id",
        filename="anim.gif",
        size_bytes=1234,
        mime_type="image/gif",
        thumb_url="https://api.telegram.org/file/botsecret/thumb.gif",
        tags=[],
    )

    voice_task = {
        "capability": "draw_generated",
        "params": {
            "prompt": "",
            "gallery_image_id": image["id"],
            "_account_id": "owner",
        },
        "source": "api",
    }
    task = await project_to_motion_task_async("dev-gallery-5", voice_task)
    assert task.get("error", {}).get("code") == "draw_failed"
    assert "unsupported image type" in str(task.get("error", {}).get("reason", "")).lower()


@pytest.mark.asyncio
async def test_draw_generated_gallery_image_id_not_found():
    voice_task = {
        "capability": "draw_generated",
        "params": {
            "prompt": "",
            "gallery_image_id": "missing",
            "_account_id": "owner",
        },
        "source": "api",
    }
    task = await project_to_motion_task_async("dev-gallery-2", voice_task)
    assert task.get("error", {}).get("code") == "draw_failed"
    assert "not found" in str(task.get("error", {}).get("reason", "")).lower()
