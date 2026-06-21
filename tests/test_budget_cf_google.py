"""CF-G-1: Cloudflare and Google budget configs, summary, and alerts."""

import logging

import budget_manager
from tests.budget_manager_helpers import reset_budget_manager_state, set_budget_usage_for_tests


def setup_function():
    reset_budget_manager_state()


def test_cf_backends_have_budget_config():
    for backend in (
        "cf_qwen_coder",
        "cf_llama70b",
        "cf_llama4",
        "cf_mistral",
        "cf_vision",
        "cf_kimi_k26",
        "cf_deepseek_r1",
        "cf_qwq",
        "cf_gptoss_120b",
        "cf_qwen3_30b",
        "cf_nemotron",
        "cf_glm47",
        "cf_gemma4",
    ):
        cfg = budget_manager.BACKEND_BUDGETS.get(backend)
        assert cfg is not None, backend
        assert cfg.daily_limit is not None and cfg.daily_limit >= 800


def test_google_flash_has_budget_config():
    cfg = budget_manager.BACKEND_BUDGETS["google_flash"]
    assert cfg.daily_limit == 1000


def test_cf_pool_usage_aggregates_cf_prefix():
    set_budget_usage_for_tests("cf_qwen_coder", 100)
    set_budget_usage_for_tests("cf_llama4", 50)
    set_budget_usage_for_tests("google_flash", 200)
    used, limit = budget_manager.get_cf_pool_usage()
    assert used == 150
    assert limit == budget_manager.CF_ACCOUNT_DAILY_LIMIT


def test_cf_pool_status_warning_at_70_percent():
    threshold = int(budget_manager.CF_ACCOUNT_DAILY_LIMIT * 0.7)
    set_budget_usage_for_tests("cf_qwen_coder", threshold)
    assert budget_manager.get_cf_pool_status() == "warning"


def test_get_usage_summary_groups_cf_and_google():
    set_budget_usage_for_tests("cf_qwen_coder", 42)
    set_budget_usage_for_tests("google_flash_lite", 10)
    summary = budget_manager.get_usage_summary()
    assert "Cloudflare" in summary
    assert "Google" in summary
    assert "cf_qwen_coder" in summary["Cloudflare"]
    assert "42/" in summary["Cloudflare"]
    assert "google_flash_lite" in summary["Google"]


def test_get_total_requests_today_sums_budgeted_usage():
    set_budget_usage_for_tests("cf_qwen_coder", 10)
    set_budget_usage_for_tests("google_flash", 5)
    assert budget_manager.get_total_requests_today() == 15


def test_record_usage_logs_on_warning_cross(caplog):
    cfg = budget_manager.BACKEND_BUDGETS["cf_qwen_coder"]
    warn_used = int(cfg.daily_limit * cfg.warn_at)
    set_budget_usage_for_tests("cf_qwen_coder", warn_used - 1)
    with caplog.at_level(logging.WARNING):
        budget_manager.record_usage("cf_qwen_coder")
    assert "budget warning backend=cf_qwen_coder" in caplog.text


def test_record_usage_logs_on_exhausted_cross(caplog):
    cfg = budget_manager.BACKEND_BUDGETS["cf_qwen_coder"]
    set_budget_usage_for_tests("cf_qwen_coder", cfg.daily_limit - 1)
    with caplog.at_level(logging.WARNING):
        budget_manager.record_usage("cf_qwen_coder")
    assert "budget exhausted backend=cf_qwen_coder" in caplog.text


def test_record_usage_logs_cf_pool_warning(caplog):
    threshold = int(budget_manager.CF_ACCOUNT_DAILY_LIMIT * budget_manager.CF_ACCOUNT_WARN_AT)
    set_budget_usage_for_tests("cf_qwen_coder", threshold - 1)
    with caplog.at_level(logging.WARNING):
        budget_manager.record_usage("cf_qwen_coder")
    assert "cf pool budget warning" in caplog.text
