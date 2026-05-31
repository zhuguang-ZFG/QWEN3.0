"""Test unified backend registry — backends.py as single source of truth.

Verifies that:
- Every backend in POOLS / DIRECT_BACKENDS / capability lists is registered in BACKENDS
- Capability helpers (backend_has_capability, is_weak_backend, etc.) work correctly
- VISION_BACKENDS, IDE_SOURCES, STRONG_MODELS are single-source imports
- GFW_BACKENDS is a single shared object across importers
- BACKENDS structure is well-formed
"""
import backends
import http_caller
import smart_router


# ── BACKENDS completeness ───────────────────────────────────────────────────────

def test_proxy_backend_set_is_shared_from_backend_registry():
    assert http_caller.GFW_BACKENDS is backends.GFW_BACKENDS
    assert smart_router.GFW_BACKENDS is backends.GFW_BACKENDS
    assert "google_flash" in backends.GFW_BACKENDS


def test_all_routing_pool_backends_registered():
    from router_v3 import POOLS

    missing = []
    for pool_name, tiers in POOLS.items():
        for tier_name, pool_backends in tiers.items():
            for b in pool_backends:
                if b not in backends.BACKENDS:
                    missing.append(f"POOLS[{pool_name}][{tier_name}]: {b}")

    assert not missing, f"POOLS backends not in BACKENDS: {missing}"


def test_all_code_orchestrator_pools_registered():
    from code_orchestrator import POOLS as CO_POOLS

    missing = []
    for pool_name, pool_backends in CO_POOLS.items():
        for b in pool_backends:
            if b not in backends.BACKENDS:
                missing.append(f"code_orchestrator.POOLS[{pool_name}]: {b}")

    assert not missing, f"Code orchestrator backends not in BACKENDS: {missing}"


def test_direct_backends_registered():
    from router_v3 import DIRECT_BACKENDS

    missing = [b for b in DIRECT_BACKENDS if b not in backends.BACKENDS]
    assert not missing, f"DIRECT_BACKENDS not in BACKENDS: {missing}"


def test_vision_backends_registered():
    missing = [b for b in backends.VISION_BACKENDS if b not in backends.BACKENDS]
    assert not missing, f"VISION_BACKENDS not in BACKENDS: {missing}"


def test_thinking_backends_registered():
    missing = [b for b in backends.THINKING_BACKENDS if b not in backends.BACKENDS]
    assert not missing, f"THINKING_BACKENDS not in BACKENDS: {missing}"


def test_strong_models_registered():
    missing = [b for b in backends.STRONG_MODELS if b not in backends.BACKENDS]
    assert not missing, f"STRONG_MODELS not in BACKENDS: {missing}"


def test_gfw_backends_registered():
    missing = [b for b in backends.GFW_BACKENDS if b not in backends.BACKENDS]
    assert not missing, f"GFW_BACKENDS not in BACKENDS: {missing}"


def test_weak_backends_registered():
    missing = [b for b in backends.WEAK_BACKENDS if b not in backends.BACKENDS]
    assert not missing, f"WEAK_BACKENDS not in BACKENDS: {missing}"


# ── IDE_SOURCES consistency ─────────────────────────────────────────────────────

def test_ide_sources_non_empty():
    assert len(backends.IDE_SOURCES) >= 10, "IDE_SOURCES should cover major IDEs"


# ── Capability helpers ───────────────────────────────────────────────────────────

def test_backend_has_capability_known_backend():
    assert backends.backend_has_capability("github_gpt4o", "vision")
    assert backends.backend_has_capability("nvidia_qwen_coder", "code")
    assert backends.backend_has_capability("scnet_ds_pro", "code")


def test_host_dependent_backends_removed_from_production_registry():
    assert "local_coder14b" not in backends.BACKENDS
    assert "scnet_large_ds_flash" not in backends.BACKENDS
    assert "mimo_web" not in backends.BACKENDS
    # M1: local_* Ollama models fully removed, no longer in DISABLED_HOST_DEPENDENT_BACKENDS
    assert "local_coder14b" not in backends.DISABLED_HOST_DEPENDENT_BACKENDS
    assert "scnet_large_ds_flash" in backends.DISABLED_HOST_DEPENDENT_BACKENDS
    assert backends.backend_has_capability("scnet_large_ds_flash", "tool_calls")


def test_backend_has_capability_unknown_backend():
    assert backends.backend_has_capability("nonexistent_backend_xyz", "code") is False


def test_backend_registry_marks_configured_vision_caps():
    assert backends.backend_has_capability("vision_joycaption", "vision")


def test_is_weak_backend():
    assert backends.is_weak_backend("chat_ubi") is True
    assert backends.is_weak_backend("pollinations") is True
    assert backends.is_weak_backend("llm7") is True
    assert backends.is_weak_backend("scnet_ds_flash") is False
    assert backends.is_weak_backend("nonexistent") is False


def test_first_backend_with_capability():
    result = backends.first_backend_with_capability(
        ["groq_llama70b", "github_gpt4o", "scnet_qwen30b"], "vision"
    )
    assert result == "github_gpt4o"

    empty = backends.first_backend_with_capability(["groq_llama70b"], "vision")
    assert empty == ""


def test_infer_key_pool_provider():
    assert backends.infer_key_pool_provider("groq_llama70b", {}) == "groq"
    assert backends.infer_key_pool_provider("or_deepseek_r1", {}) == "openrouter"
    assert backends.infer_key_pool_provider("github_gpt4o", {}) == "github"
    assert backends.infer_key_pool_provider("unknown_backend", {}) == ""


# ── BACKENDS structure ───────────────────────────────────────────────────────────

def test_backends_dict_non_empty():
    assert len(backends.BACKENDS) >= 150, "BACKENDS should have 150+ entries"


def test_every_backend_has_url():
    missing = [k for k, v in backends.BACKENDS.items() if not v.get("url")]
    assert not missing, f"Backends without URL: {missing}"


def test_every_backend_has_fmt():
    missing = [k for k, v in backends.BACKENDS.items() if not v.get("fmt")]
    assert not missing, f"Backends without fmt: {missing}"


def test_every_backend_has_model():
    missing = [k for k, v in backends.BACKENDS.items() if not v.get("model")]
    assert not missing, f"Backends without model: {missing}"


# ── Cap detection ────────────────────────────────────────────────────────────────

def test_code_capable_backends_all_registered():
    """Every CODE_CAPABLE_BACKENDS entry must be in BACKENDS."""
    missing = [b for b in backends.CODE_CAPABLE_BACKENDS if b not in backends.BACKENDS]
    assert not missing, f"CODE_CAPABLE_BACKENDS not in BACKENDS: {missing}"


def test_detect_caps_code_backends_have_code_cap():
    for b in backends.CODE_CAPABLE_BACKENDS:
        caps = backends.detect_caps(b)
        assert "code" in caps, f"{b} should have 'code' cap"


def test_detect_caps_returns_list():
    caps = backends.detect_caps("longcat")
    assert isinstance(caps, list)
    assert len(caps) >= 1


def test_vision_backends_have_vision_cap():
    for b in backends.VISION_BACKENDS:
        caps = backends.detect_caps(b)
        assert "vision" in caps, f"VISION backend {b} should have 'vision' cap"


# ── Vendor / Tier / Protocol detection ───────────────────────────────────────────

def test_detect_vendor_known():
    assert backends.detect_vendor("https://api.groq.com/openai/v1") == "Groq"
    assert backends.detect_vendor("https://api.longcat.chat/anthropic/v1/messages") == "LongCat"
    assert (
        backends.detect_vendor("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
        == "Google"
    )


def test_detect_tier_returns_string():
    tier = backends.detect_tier("https://api.longcat.chat/anthropic/v1/messages", "longcat")
    assert isinstance(tier, str)
    assert tier != "Unknown"


def test_detect_protocol():
    assert backends.detect_protocol("anthropic") == "Anthropic"
    assert backends.detect_protocol("openai") == "OpenAI"


# ── VISION_BACKENDS single source ────────────────────────────────────────────────

def test_vision_handler_uses_backends_source():
    import vision_handler

    assert vision_handler.VISION_BACKENDS is backends.VISION_BACKENDS, (
        "vision_handler.VISION_BACKENDS should be backends.VISION_BACKENDS"
    )


def test_smart_router_uses_backends_vision_source():
    assert smart_router.VISION_BACKENDS is backends.VISION_BACKENDS, (
        "smart_router.VISION_BACKENDS should be backends.VISION_BACKENDS"
    )


# ── IDE_SOURCES single source ────────────────────────────────────────────────────

def test_router_v3_uses_backends_ide_sources():
    import router_v3

    assert router_v3.IDE_SOURCES is backends.IDE_SOURCES, (
        "router_v3.IDE_SOURCES should be backends.IDE_SOURCES"
    )


# ── STRONG_MODELS single source ──────────────────────────────────────────────────

def test_skills_injector_uses_backends_strong_models():
    import skills_injector

    assert skills_injector.STRONG_MODELS is backends.STRONG_MODELS, (
        "skills_injector.STRONG_MODELS should be backends.STRONG_MODELS"
    )


# ── is_enabled / set_enabled ─────────────────────────────────────────────────────

def test_backend_is_enabled_default_true():
    assert backends.is_enabled("scnet_ds_flash") is True
    assert backends.is_enabled("nonexistent_backend") is True


def test_backend_set_enabled_and_is_enabled():
    backends.set_enabled("scnet_ds_flash", False)
    assert backends.is_enabled("scnet_ds_flash") is False
    backends.set_enabled("scnet_ds_flash", True)
    assert backends.is_enabled("scnet_ds_flash") is True


# ── Reflection uses registry ─────────────────────────────────────────────────────

def test_reflection_uses_backend_registry_capabilities(monkeypatch):
    from context_pipeline.reflection import reflect_on_routing

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
