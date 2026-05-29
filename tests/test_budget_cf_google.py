"""CF-G-1: Cloudflare and Google budget configs, summary, and alerts."""

from unittest.mock import patch

import budget_manager


def setup_function():
    budget_manager.reset_for_tests()
    import telegram_notify

    telegram_notify.reset_budget_alerts_for_tests()


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
    budget_manager.set_usage_for_tests("cf_qwen_coder", 100)
    budget_manager.set_usage_for_tests("cf_llama4", 50)
    budget_manager.set_usage_for_tests("google_flash", 200)
    used, limit = budget_manager.get_cf_pool_usage()
    assert used == 150
    assert limit == budget_manager.CF_ACCOUNT_DAILY_LIMIT


def test_cf_pool_status_warning_at_70_percent():
    threshold = int(budget_manager.CF_ACCOUNT_DAILY_LIMIT * 0.7)
    budget_manager.set_usage_for_tests("cf_qwen_coder", threshold)
    assert budget_manager.get_cf_pool_status() == "warning"


def test_get_usage_summary_groups_cf_and_google():
    budget_manager.set_usage_for_tests("cf_qwen_coder", 42)
    budget_manager.set_usage_for_tests("google_flash_lite", 10)
    summary = budget_manager.get_usage_summary()
    assert "Cloudflare" in summary
    assert "Google" in summary
    assert "cf_qwen_coder" in summary["Cloudflare"]
    assert "42/" in summary["Cloudflare"]
    assert "google_flash_lite" in summary["Google"]


def test_get_total_requests_today_sums_budgeted_usage():
    budget_manager.set_usage_for_tests("cf_qwen_coder", 10)
    budget_manager.set_usage_for_tests("google_flash", 5)
    assert budget_manager.get_total_requests_today() == 15


@patch("telegram_notify.notify_budget_threshold")
def test_record_usage_notifies_on_warning_cross(mock_notify):
    cfg = budget_manager.BACKEND_BUDGETS["cf_qwen_coder"]
    warn_used = int(cfg.daily_limit * cfg.warn_at)
    budget_manager.set_usage_for_tests("cf_qwen_coder", warn_used - 1)
    budget_manager.record_usage("cf_qwen_coder")
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs.get("level") == "warning"


@patch("telegram_notify.notify_budget_threshold")
def test_record_usage_notifies_on_exhausted_cross(mock_notify):
    cfg = budget_manager.BACKEND_BUDGETS["cf_qwen_coder"]
    budget_manager.set_usage_for_tests("cf_qwen_coder", cfg.daily_limit - 1)
    budget_manager.record_usage("cf_qwen_coder")
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs.get("level") == "exhausted"


@patch("telegram_notify.notify_budget_threshold")
def test_record_usage_notifies_cf_pool_warning(mock_notify):
    threshold = int(budget_manager.CF_ACCOUNT_DAILY_LIMIT * budget_manager.CF_ACCOUNT_WARN_AT)
    budget_manager.set_usage_for_tests("cf_qwen_coder", threshold - 1)
    budget_manager.record_usage("cf_qwen_coder")
    levels = [c.kwargs.get("level") for c in mock_notify.call_args_list]
    assert "pool_warning" in levels
