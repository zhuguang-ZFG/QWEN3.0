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


def test_image_generator_has_live_targets():
    spec = get_role_spec("image_generator")
    assert spec is not None
    assert spec.live_pytest_targets == ("tests/test_dashscope_image_live.py",)


def test_evaluate_role_include_live_merges_targets(monkeypatch):
    from scripts.eval_device_model_role import evaluate_role

    spec = get_role_spec("image_generator")
    assert spec is not None
    calls: list[tuple[str, ...]] = []

    def fake_run(targets: tuple[str, ...]):
        calls.append(targets)
        return 7, 0, 0, "pytest ..."

    monkeypatch.setattr("scripts.eval_device_model_role._run_pytest", fake_run)
    evaluate_role(spec, include_live=True)
    assert "tests/test_dashscope_image_live.py" in calls[0]
