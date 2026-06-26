import pytest

from brand_config import (
    CAPABILITY_BULLETS_CN,
    CAPABILITY_SUMMARY_CN,
    COMPANY_NAME_CN,
    PUBLIC_MODEL_NAME,
    PUBLIC_MODEL_NAME_CN,
)
from device_gateway.intent import DANGEROUS_CAPABILITIES
from prompt_engineering.layers import PROMPT_VERSION, build_role_layer, compose_system_prompt
from prompt_engineering.registry import _BASE_DIR, _CACHE, load_prompt_template

SCENARIOS = ["coding", "chat", "vision", "device_draw", "device_write", "device_control"]


@pytest.fixture(autouse=True)
def _clear_template_cache():
    """Keep the mtime cache empty at the start of every test."""
    _CACHE.clear()
    yield
    _CACHE.clear()


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_role_templates_load(scenario):
    template = load_prompt_template("layers", f"role.{scenario}")
    assert isinstance(template, str)
    assert template.strip()


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_skill_templates_load(scenario):
    template = load_prompt_template("layers", f"skill.{scenario}")
    assert isinstance(template, str)
    assert template.strip()


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_role_layer_contains_expected_placeholders(scenario):
    role = build_role_layer("", scenario)
    assert PUBLIC_MODEL_NAME in role
    if scenario == "chat":
        assert PUBLIC_MODEL_NAME_CN in role
        assert COMPANY_NAME_CN in role
        for bullet in CAPABILITY_BULLETS_CN.values():
            assert bullet in role
    elif scenario == "coding":
        assert CAPABILITY_SUMMARY_CN in role
    elif scenario == "device_control":
        for cap in DANGEROUS_CAPABILITIES:
            assert cap in role


def test_missing_template_raises_clear_error():
    with pytest.raises(KeyError, match="layers.missing_role.xxx"):
        load_prompt_template("layers", "missing_role.xxx")


def test_missing_file_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "prompt_engineering.registry._BASE_DIR",
        tmp_path,
    )
    with pytest.raises(FileNotFoundError, match="Prompt template file not found"):
        load_prompt_template("layers", "role.chat")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_compose_system_prompt_returns_non_empty_string(scenario):
    prompt = compose_system_prompt(ide="", scenario=scenario, code_context="")
    assert isinstance(prompt, str)
    assert prompt.strip()
    assert PROMPT_VERSION in prompt


def test_cache_invalidation_reloads_on_mtime_change():
    path = _BASE_DIR / "layers.yaml"
    # Seed cache with stale entry
    _CACHE[path] = (0.0, {"role": {"chat": "stale"}})
    loaded = load_prompt_template("layers", "role.chat")
    assert loaded != "stale"
    assert "{name}" in loaded
    assert "{name_cn}" in loaded
