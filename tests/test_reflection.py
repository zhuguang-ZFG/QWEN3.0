from context_pipeline.reflection import reflect_on_routing, ReflectionResult


def test_reflection_no_correction_for_strong_coding_backend():
    result = reflect_on_routing(
        backend="scnet_ds_pro",
        scenario="coding",
        ide="Cursor",
        available_backends=["scnet_ds_pro", "chat_ubi"],
    )
    assert not result.was_corrected
    assert result.corrected_backend == "scnet_ds_pro"


def test_reflection_corrects_weak_backend_for_ide_coding():
    result = reflect_on_routing(
        backend="chat_ubi",
        scenario="coding",
        ide="Cursor",
        available_backends=["chat_ubi", "scnet_ds_pro", "pollinations"],
    )
    assert result.was_corrected
    assert result.corrected_backend == "scnet_ds_pro"
    assert "weak backend" in result.reason


def test_reflection_corrects_non_vision_backend_for_vision():
    result = reflect_on_routing(
        backend="groq_llama70b",
        scenario="vision",
        ide="Cursor",
        available_backends=["groq_llama70b", "github_gpt4o"],
    )
    assert result.was_corrected
    assert result.corrected_backend == "github_gpt4o"
    assert "vision" in result.reason.lower()


def test_reflection_no_correction_for_chat():
    result = reflect_on_routing(
        backend="chat_ubi",
        scenario="chat",
        ide="",
        available_backends=["chat_ubi", "pollinations"],
    )
    assert not result.was_corrected


def test_reflection_upgrades_general_to_coding_capable():
    result = reflect_on_routing(
        backend="pollinations",
        scenario="coding",
        ide="",
        available_backends=["pollinations", "cf_qwen_coder"],
    )
    assert result.was_corrected
    assert result.corrected_backend == "cf_qwen_coder"
    assert "upgraded" in result.reason.lower()
