"""Tests for device model role admission eval tooling."""

from pathlib import Path

from scripts.device_model_role_eval_specs import ROLE_SPECS, get_role_spec


def test_admission_template_exists():
    path = Path("docs/model_admission/TEMPLATE.md")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "准入标准" in text
    assert "eval_device_model_role.py" in text


def test_role_specs_cover_roadmap_roles():
    ids = {spec.role_id for spec in ROLE_SPECS}
    for required in (
        "intent_parser",
        "text_planner",
        "prompt_enhancer",
        "image_generator",
        "vectorizer",
        "vision_analyzer",
        "recovery_explainer",
    ):
        assert required in ids


def test_get_role_spec_known():
    spec = get_role_spec("intent_parser")
    assert spec is not None
    assert spec.backend_id == "deterministic_intent"


def test_eval_script_lists_deferred_roles(tmp_path, monkeypatch):
    from scripts.eval_device_model_role import evaluate_role

    defer = get_role_spec("prompt_enhancer")
    assert defer is not None
    result = evaluate_role(defer)
    assert result.verdict == "defer"
    assert result.fixture_count == 0
