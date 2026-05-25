from coding_eval import EvalResult
from web_reverse_eval import (
    cap_backend_timeouts,
    discover_web_reverse_backends,
    safe_web_reverse_cases,
    summarize_results,
    write_markdown_report,
)


def test_discover_web_reverse_backends_uses_inventory_and_registry_only_candidates():
    inventory = [
        {
            "id": "duck_ai",
            "lima_backends": ["ddg_gpt4o_mini", "missing_backend"],
        }
    ]
    backends = {
        "ddg_gpt4o_mini": {
            "url": "http://localhost:4500/v1/chat/completions",
            "key": "none",
            "model": "gpt-4o-mini",
        },
        "mimo_web": {
            "url": "http://localhost:4507/v1/chat/completions",
            "key": "none",
            "model": "mimo-web",
        },
        "normal_api": {
            "url": "https://api.example.test/v1/chat/completions",
            "key": "none",
            "model": "chat",
        },
    }

    selected = discover_web_reverse_backends(inventory, backends)

    assert selected == ["ddg_gpt4o_mini", "mimo_web"]


def test_discover_web_reverse_backends_does_not_select_direct_kimi_named_apis():
    selected = discover_web_reverse_backends(
        [],
        {
            "cf_kimi_k26": {
                "url": "https://api.cloudflare.com/client/v4/accounts/a/ai/v1/chat/completions",
                "key": "k",
                "model": "@cf/moonshotai/kimi-k2.6",
            },
            "stock_kimi_k2": {
                "url": "https://stock.example.test/v1/chat/completions",
                "key": "1",
                "model": "moonshotai/kimi-k2",
            },
            "kimi_thinking": {
                "url": "http://localhost:4504/v1/chat/completions",
                "key": "none",
                "model": "kimi-thinking",
            },
        },
    )

    assert selected == ["kimi_thinking"]


def test_safe_web_reverse_cases_do_not_include_private_project_context():
    prompts = "\n".join(case.prompt for case in safe_web_reverse_cases())

    assert "D:\\" not in prompts
    assert "router_v3.py" not in prompts
    assert "LiMa" not in prompts
    assert "secret" not in prompts.lower()


def test_cap_backend_timeouts_only_lowers_selected_backend_timeouts():
    backends = {
        "slow_web": {"timeout": 120},
        "fast_web": {"timeout": 8},
        "other": {"timeout": 90},
    }

    changed = cap_backend_timeouts(backends, ["slow_web", "fast_web"], 15)

    assert changed == 1
    assert backends["slow_web"]["timeout"] == 15
    assert backends["fast_web"]["timeout"] == 8
    assert backends["other"]["timeout"] == 90


def test_summarize_results_recommends_code_medium_for_clean_high_scores():
    results = [
        EvalResult("mimo_web", "a", 95, 1200, True, [], "ok"),
        EvalResult("mimo_web", "b", 90, 1800, True, [], "ok"),
        EvalResult("mimo_web", "c", 88, 1600, True, [], "ok"),
    ]

    summaries = summarize_results(results)

    assert summaries["mimo_web"]["recommendation"] == "code_medium_candidate"
    assert summaries["mimo_web"]["passes"] == 3


def test_summarize_results_requires_full_batch_before_route_candidate_status():
    results = [EvalResult("mimo_web", "a", 100, 1200, True, [], "ok")]

    summaries = summarize_results(results)

    assert summaries["mimo_web"]["recommendation"] == "phase2_required"


def test_summarize_results_recommends_code_floor_for_two_passing_cases():
    results = [
        EvalResult("ddg_gpt5_mini", "a", 90, 1200, True, [], "ok"),
        EvalResult("ddg_gpt5_mini", "b", 75, 1800, True, [], "ok"),
        EvalResult("ddg_gpt5_mini", "c", 40, 1600, False, ["json parse failed"], ""),
    ]

    summaries = summarize_results(results)

    assert summaries["ddg_gpt5_mini"]["recommendation"] == "code_floor_candidate"


def test_summarize_results_disables_auth_or_quota_failures():
    results = [
        EvalResult(
            "kimi",
            "a",
            0,
            500,
            False,
            ["call failed: BackendError: anonymous quota exceeded"],
            "",
        ),
        EvalResult(
            "kimi",
            "b",
            0,
            500,
            False,
            ["call failed: BackendError: auth expired"],
            "",
        ),
    ]

    summaries = summarize_results(results)

    assert summaries["kimi"]["recommendation"] == "disabled_auth_or_quota"


def test_summarize_results_disables_cookie_failures_as_auth():
    results = [
        EvalResult(
            "mimo_web",
            "a",
            0,
            500,
            False,
            ["call failed: BackendError: mimo_web returned error response: [MiMo Cookie expired]"],
            "",
        )
    ]

    summaries = summarize_results(results)

    assert summaries["mimo_web"]["recommendation"] == "disabled_auth_or_quota"


def test_write_markdown_report_handles_summary_notes(tmp_path):
    results = [
        EvalResult("mimo_web", "a", 40, 100, False, ["json parse failed"], "")
    ]
    summaries = summarize_results(results)
    out = tmp_path / "report.md"

    write_markdown_report(results, summaries, out)

    content = out.read_text(encoding="utf-8")
    assert "`mimo_web`" in content
    assert "json parse failed" in content
