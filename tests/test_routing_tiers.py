"""Tests for routing_tiers.py — model tier definitions."""

from routing_tiers import get_tier, tier_for_difficulty


def test_free_tier_for_known_free_backend():
    assert get_tier("chinamobile") == "free"
    assert get_tier("longcat_chat") == "free"


def test_budget_tier_for_known_budget_backend():
    assert get_tier("groq_llama8b") == "budget"
    assert get_tier("scnet_ds_flash") == "budget"


def test_premium_tier_for_known_premium_backend():
    assert get_tier("scnet_ds_pro") == "premium"
    assert get_tier("hermes_agent") == "premium"


def test_unknown_backend_defaults_to_budget():
    assert get_tier("some_unknown_backend") == "budget"


def test_low_difficulty_maps_to_free():
    assert tier_for_difficulty(10) == "free"
    assert tier_for_difficulty(30) == "free"


def test_medium_difficulty_maps_to_budget():
    assert tier_for_difficulty(50) == "budget"
    assert tier_for_difficulty(70) == "budget"


def test_high_difficulty_maps_to_premium():
    assert tier_for_difficulty(80) == "premium"
    assert tier_for_difficulty(100) == "premium"


def test_tier_boundaries():
    """Verify boundary values for tier transitions."""
    assert tier_for_difficulty(0) == "free"
    assert tier_for_difficulty(31) == "budget"
    assert tier_for_difficulty(71) == "premium"
