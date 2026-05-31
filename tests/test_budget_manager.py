"""Tests for budget_manager.py — cost class, token telemetry, quota scoring."""
import budget_manager


def setup_function():
    budget_manager.reset_for_tests()


# ── Cost class ─────────────────────────────────────────────────────────────────

def test_local_backends_are_free():
    # M1: local_* deleted; M6: deepseek_free deleted. Use active free backends.
    for b in ['scnet_ds_flash', 'opencode_stealth', 'ovh_llama70b']:
        assert budget_manager.get_cost_class(b) == 'free', f'{b} should be free'


def test_free_backends_are_free():
    for b in ['scnet_ds_flash', 'scnet_qwen235b', 'opencode_stealth', 'ovh_llama70b']:
        assert budget_manager.get_cost_class(b) == 'free', f'{b} should be free'


def test_unknown_backend_is_limited():
    assert budget_manager.get_cost_class('some_random_new_backend') == 'limited'


def test_free_backends_never_block():
    # M1: local_coder14b deleted. Use only active free backends.
    for b in ['scnet_ds_flash', 'opencode_stealth', 'ovh_llama70b']:
        assert budget_manager.should_track_cost(b) is False, f'{b} should not block'
        assert budget_manager.is_budget_available(b) is True


# ── Token telemetry ────────────────────────────────────────────────────────────

def test_record_token_usage_basic():
    budget_manager.record_token_usage('github_gpt4o', prompt_tokens=100, completion_tokens=50)
    usage = budget_manager.get_token_usage('github_gpt4o')
    assert usage['prompt'] == 100
    assert usage['completion'] == 50
    assert usage['requests'] == 1


def test_record_token_usage_accumulates():
    budget_manager.record_token_usage('mistral_large', prompt_tokens=100, completion_tokens=30)
    budget_manager.record_token_usage('mistral_large', prompt_tokens=200, completion_tokens=60)
    usage = budget_manager.get_token_usage('mistral_large')
    assert usage['prompt'] == 300
    assert usage['completion'] == 90
    assert usage['requests'] == 2


def test_record_token_usage_skips_free_backends():
    budget_manager.record_token_usage('scnet_ds_flash', prompt_tokens=100, completion_tokens=50)
    usage = budget_manager.get_token_usage('scnet_ds_flash')
    assert usage['prompt'] == 0
    assert usage['requests'] == 0


def test_record_token_usage_skips_zero_values():
    budget_manager.record_token_usage('github_gpt4o', prompt_tokens=0, completion_tokens=0)
    usage = budget_manager.get_token_usage('github_gpt4o')
    assert usage['requests'] == 0


def test_get_token_usage_all_backends():
    budget_manager.record_token_usage('github_gpt4o', prompt_tokens=50, completion_tokens=10)
    budget_manager.record_token_usage('mistral_large', prompt_tokens=100, completion_tokens=30)
    all_usage = budget_manager.get_token_usage()
    assert 'github_gpt4o' in all_usage
    assert 'mistral_large' in all_usage
    assert all_usage['github_gpt4o']['requests'] == 1


def test_get_token_usage_unknown_backend():
    usage = budget_manager.get_token_usage('nonexistent_xyz')
    assert usage['prompt'] == 0
    assert usage['requests'] == 0


# ── Budget / quota ─────────────────────────────────────────────────────────────

def test_remaining_quota_score_no_config():
    assert budget_manager.get_remaining_quota_score('scnet_ds_flash') == 1.0


def test_remaining_quota_score_exhausted():
    budget_manager.set_usage_for_tests('longcat_lite', 3000)
    assert budget_manager.get_remaining_quota_score('longcat_lite') == 0.0


def test_budget_status_normal_warning_exhausted():
    assert budget_manager.get_budget_status('longcat_lite') == 'normal'

    budget_manager.set_usage_for_tests('longcat_lite', 2500)  # 2500/3000 > 0.8 → warning
    assert budget_manager.get_budget_status('longcat_lite') == 'warning'

    budget_manager.set_usage_for_tests('longcat_lite', 3000)  # exhausted
    assert budget_manager.get_budget_status('longcat_lite') == 'exhausted'
    assert budget_manager.is_budget_available('longcat_lite') is False


def test_reset_clears_all_state():
    budget_manager.record_token_usage('github_gpt4o', prompt_tokens=100)
    budget_manager.set_usage_for_tests('longcat_lite', 500)
    budget_manager.reset_for_tests()
    assert budget_manager.get_token_usage('github_gpt4o')['requests'] == 0
    assert budget_manager.get_budget_status('longcat_lite') == 'normal'
