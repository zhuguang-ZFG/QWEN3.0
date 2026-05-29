"""Tests for router_image (CQ-014 slice 7)."""

import router_image


def test_detect_image_intent_chinese_draw():
    is_image, prompt = router_image.detect_image_intent("帮我画一只猫")
    assert is_image is True
    assert "猫" in prompt


def test_detect_image_intent_english_generate():
    is_image, prompt = router_image.detect_image_intent("generate an image of a sunset")
    assert is_image is True
    assert "sunset" in prompt.lower()


def test_detect_image_intent_non_image():
    is_image, prompt = router_image.detect_image_intent("explain quicksort in python")
    assert is_image is False
    assert prompt == ""


def test_detect_image_intent_reexported_via_smart_router():
    import smart_router

    is_image, _ = smart_router.detect_image_intent("帮我画一只狗")
    assert is_image is True
