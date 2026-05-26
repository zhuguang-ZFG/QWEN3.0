"""Tests for backend admission overlay routing (CF-G-2)."""

import json
from pathlib import Path

import backends
import router_v3
from backend_admission_store import (
    AdmissionOverlay,
    apply_startup,
    dynamic_admission_enabled,
    get_routing_overlays_for_pool,
    save_store,
    upsert_overlay,
)


def _write_store(path: Path, overlays: list[dict], watchlist: list[dict] | None = None) -> None:
    save_store({"overlays": overlays, "watchlist": watchlist or []}, path)


def test_dynamic_admission_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LIMA_DYNAMIC_ADMISSION", raising=False)
    assert dynamic_admission_enabled() is False
    assert get_routing_overlays_for_pool("chat") == []


def test_get_routing_overlays_for_chat_pool(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LIMA_DYNAMIC_ADMISSION", "1")
    _write_store(tmp_path / "admission.json", [{
        "backend_key": "cf_llama3_8b",
        "provider": "cloudflare",
        "model_id": "@cf/meta/llama-3-8b-instruct",
        "tier": "medium",
        "admission_status": "admitted_late_fallback",
        "enabled": True,
    }])
    keys = get_routing_overlays_for_pool("chat", tmp_path / "admission.json")
    assert keys == ["cf_llama3_8b"]


def test_code_pool_skips_private_code_false_overlay(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LIMA_DYNAMIC_ADMISSION", "1")
    _write_store(tmp_path / "admission.json", [{
        "backend_key": "cf_llama3_8b",
        "provider": "cloudflare",
        "model_id": "@cf/meta/llama-3-8b-instruct",
        "tier": "medium",
        "admission_status": "admitted_late_fallback",
        "private_code_allowed": False,
        "enabled": True,
    }])
    assert get_routing_overlays_for_pool("code", tmp_path / "admission.json") == []


def test_code_pool_includes_floor_overlay(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LIMA_DYNAMIC_ADMISSION", "1")
    _write_store(tmp_path / "admission.json", [{
        "backend_key": "cf_new_coder",
        "provider": "cloudflare",
        "model_id": "@cf/qwen/new-coder",
        "tier": "floor",
        "admission_status": "admitted_late_fallback",
        "private_code_allowed": True,
        "enabled": True,
    }])
    assert "cf_new_coder" in get_routing_overlays_for_pool("code", tmp_path / "admission.json")


def test_select_backends_includes_overlay_in_medium_tier(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LIMA_DYNAMIC_ADMISSION", "1")
    overlay_path = tmp_path / "admission.json"
    _write_store(overlay_path, [{
        "backend_key": "cf_overlay_test",
        "provider": "cloudflare",
        "model_id": "@cf/meta/llama-3-8b-instruct",
        "tier": "medium",
        "admission_status": "admitted_late_fallback",
        "enabled": True,
    }])
    monkeypatch.setattr("backend_admission_store.DEFAULT_PATH", overlay_path)
    monkeypatch.setitem(router_v3.POOLS["chat"], "strong", [])
    monkeypatch.setitem(router_v3.POOLS["chat"], "medium", [])
    monkeypatch.setitem(router_v3.POOLS["chat"], "floor", ["chat_ubi"])

    selected = router_v3.select_backends("chat", {"chat_ubi": "healthy"})
    assert "cf_overlay_test" in selected


def test_apply_startup_disables_watchlist_backend(tmp_path: Path, monkeypatch):
    store = tmp_path / "admission.json"
    store.write_text(json.dumps({
        "watchlist": [{
            "backend_key": "cfai_mistral",
            "reason": "test disable",
            "action": "disable",
        }],
        "overlays": [],
    }), encoding="utf-8")
    backends.set_enabled("cfai_mistral", True)
    try:
        apply_startup(store)
        assert backends.is_enabled("cfai_mistral") is False
    finally:
        backends.set_enabled("cfai_mistral", True)


def test_upsert_overlay_replaces_existing(tmp_path: Path):
    path = tmp_path / "admission.json"
    overlay = AdmissionOverlay(
        backend_key="cf_test",
        provider="cloudflare",
        model_id="@cf/test/model",
        tier="medium",
    )
    upsert_overlay(overlay, path)
    upsert_overlay(AdmissionOverlay(
        backend_key="cf_test",
        provider="cloudflare",
        model_id="@cf/test/model-v2",
        tier="floor",
    ), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["overlays"]) == 1
    assert data["overlays"][0]["tier"] == "floor"
