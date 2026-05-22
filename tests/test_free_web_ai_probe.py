import json

from scripts.probe_free_web_ai import load_candidates, normalize_error, write_results


def test_normalize_error_maps_known_quota_and_auth_failures():
    assert normalize_error(429, "too many requests") == "rate_limited"
    assert normalize_error(401, "Unauthorized") == "auth_expired"
    assert normalize_error(403, "forbidden") == "auth_expired"
    assert (
        normalize_error(500, "chat.anonymous_usage_exceeded")
        == "manual_refresh_required"
    )
    assert normalize_error(200, "daily quota exhausted") == "quota_exhausted"


def test_normalize_error_maps_blocking_timeout_and_unknown():
    assert normalize_error(None, "request timeout after 30s") == "timeout"
    assert normalize_error(503, "captcha required") == "blocked"
    assert normalize_error(520, "cloudflare challenge") == "blocked"
    assert normalize_error(500, "upstream exploded") == "provider_error"
    assert normalize_error(418, "weird") == "unknown_error"


def test_load_candidates_reads_registry(tmp_path):
    path = tmp_path / "candidates.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "duck_ai",
                    "url": "https://duck.ai/chat",
                    "trust": "medium-high",
                    "enabled": False,
                    "private_code_allowed": False,
                },
                {
                    "id": "heck_ai",
                    "url": "https://heck.ai/zh",
                    "trust": "medium",
                    "enabled": False,
                    "private_code_allowed": False,
                },
            ]
        ),
        encoding="utf-8",
    )

    candidates = load_candidates(path)

    assert len(candidates) == 2
    assert candidates[0]["id"] == "duck_ai"
    assert candidates[0]["enabled"] is False
    assert candidates[0]["private_code_allowed"] is False


def test_write_results_creates_parent_and_json(tmp_path):
    out = tmp_path / "nested" / "results.json"
    results = [{"id": "duck_ai", "status": "ok", "latency_ms": 123}]

    write_results(out, results)

    assert json.loads(out.read_text(encoding="utf-8")) == results
