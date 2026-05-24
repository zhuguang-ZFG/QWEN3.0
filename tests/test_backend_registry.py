import backends
import http_caller
import smart_router
from context_pipeline.reflection import reflect_on_routing


def test_proxy_backend_set_is_shared_from_backend_registry():
    assert http_caller.GFW_BACKENDS is backends.GFW_BACKENDS
    assert smart_router.GFW_BACKENDS is backends.GFW_BACKENDS
    assert "google_flash" in backends.GFW_BACKENDS


def test_reflection_uses_backend_registry_capabilities(monkeypatch):
    monkeypatch.setitem(
        backends.BACKENDS,
        "unit_code_backend",
        {
            "url": "https://example.test/v1/chat/completions",
            "key": "none",
            "model": "unit-code",
            "fmt": "openai",
            "caps": ["code"],
        },
    )

    result = reflect_on_routing(
        backend="pollinations",
        scenario="coding",
        ide="",
        available_backends=["pollinations", "unit_code_backend"],
    )

    assert result.was_corrected
    assert result.corrected_backend == "unit_code_backend"


def test_backend_registry_marks_configured_vision_caps():
    assert backends.backend_has_capability("vision_joycaption", "vision")
