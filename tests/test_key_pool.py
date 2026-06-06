import time

import key_pool


def setup_function():
    key_pool.clear_pools()


def teardown_function():
    key_pool.clear_pools()


# ── Snapshot redaction ──────────────────────────────────────────────────────────

def test_pool_snapshot_redacts_key_material():
    key_pool.register_pool(
        "unit",
        [
            {"key": "sk-secret-alpha", "weight": 2},
            {"key": "sk-secret-beta", "weight": 1},
        ],
    )

    snapshot = key_pool.pool_snapshot("unit")

    assert snapshot["provider"] == "unit"
    assert snapshot["total"] == 2
    assert snapshot["active"] == 2
    assert snapshot["cooled"] == 0
    assert snapshot["blocked"] == 0
    assert snapshot["entries"][0]["key_id"].endswith(":lpha")
    assert snapshot["entries"][1]["key_id"].endswith(":beta")
    assert "sk-secret-alpha" not in str(snapshot)
    assert "sk-secret-beta" not in str(snapshot)


def test_pool_snapshot_reports_cooldown_and_block_counts():
    key_pool.register_pool(
        "unit",
        [
            {"key": "sk-rate-limited"},
            {"key": "sk-blocked"},
            {"key": "sk-active"},
        ],
    )

    key_pool.report_key_result("unit", "sk-rate-limited", False, error_code=429, retry_after=30)
    key_pool.report_key_result("unit", "sk-blocked", False, error_code=401)
    snapshot = key_pool.pool_snapshot("unit")

    assert snapshot["active"] == 1
    assert snapshot["cooled"] == 1
    assert snapshot["blocked"] == 1
    statuses = {entry["key_id"]: entry["status"] for entry in snapshot["entries"]}
    assert set(statuses.values()) == {"active", "cooled", "blocked"}
    cooled = next(entry for entry in snapshot["entries"] if entry["status"] == "cooled")
    assert cooled["cool_remaining_sec"] > 0
    assert cooled["consecutive_429"] == 1


def test_global_pool_snapshot_lists_providers():
    key_pool.register_pool("a", [{"key": "sk-a"}])
    key_pool.register_pool("b", [{"key": "sk-b"}])

    snapshot = key_pool.pool_snapshot()

    assert set(snapshot["providers"]) == {"a", "b"}


# ── SWRR rotation ──────────────────────────────────────────────────────────────

def test_swrr_selects_different_keys_across_calls():
    key_pool.register_pool("unit", [
        {"key": "sk-alpha", "weight": 1},
        {"key": "sk-beta", "weight": 1},
    ])

    keys = {key_pool.get_key("unit") for _ in range(20)}
    assert keys == {"sk-alpha", "sk-beta"}, f"SWRR should select both keys, got {keys}"


def test_swrr_respects_weight_distribution():
    key_pool.register_pool("unit", [
        {"key": "sk-heavy", "weight": 9},
        {"key": "sk-light", "weight": 1},
    ])

    counts = {"sk-heavy": 0, "sk-light": 0}
    for _ in range(100):
        k = key_pool.get_key("unit")
        counts[k] += 1

    assert counts["sk-heavy"] > counts["sk-light"], f"heavy key should win more often: {counts}"


# ── Exhaustion ─────────────────────────────────────────────────────────────────

def test_is_exhausted_no_pool():
    assert key_pool.is_exhausted("nonexistent") is True


def test_is_exhausted_all_active():
    key_pool.register_pool("unit", [{"key": "sk-a"}, {"key": "sk-b"}])
    assert key_pool.is_exhausted("unit") is False


def test_is_exhausted_all_blocked():
    key_pool.register_pool("unit", [
        {"key": "sk-a"},
        {"key": "sk-b"},
    ])
    key_pool.report_key_result("unit", "sk-a", False, error_code=401)
    key_pool.report_key_result("unit", "sk-b", False, error_code=401)

    assert key_pool.is_exhausted("unit") is True
    assert key_pool.get_key("unit") is None


def test_is_exhausted_all_cooled():
    key_pool.register_pool("unit", [
        {"key": "sk-a"},
        {"key": "sk-b"},
    ])
    key_pool.report_key_result("unit", "sk-a", False, error_code=429, retry_after=60)
    key_pool.report_key_result("unit", "sk-b", False, error_code=429, retry_after=60)

    assert key_pool.is_exhausted("unit") is True


# ── 429 → day-level cooldown after threshold ───────────────────────────────────

def test_consecutive_429_triggers_day_level_cooldown():
    key_pool.register_pool("unit", [{"key": "sk-spam"}])

    for _ in range(5):
        key_pool.report_key_result("unit", "sk-spam", False, error_code=429, retry_after=1)

    snapshot = key_pool.pool_snapshot("unit")
    entry = snapshot["entries"][0]
    assert entry["status"] == "cooled"
    # Day-level cooldown should be > 10 min
    assert entry["cool_remaining_sec"] > 600


# ── 401/403 → permanent block ──────────────────────────────────────────────────

def test_401_blocks_key_permanently():
    key_pool.register_pool("unit", [{"key": "sk-leaked"}])
    key_pool.report_key_result("unit", "sk-leaked", False, error_code=401)

    snapshot = key_pool.pool_snapshot("unit")
    assert snapshot["entries"][0]["status"] == "blocked"
    assert snapshot["active"] == 0

    # Should stay blocked — no key to return
    assert key_pool.get_key("unit") is None


# ── Success resets 429 counter ──────────────────────────────────────────────────

def test_success_resets_consecutive_429():
    key_pool.register_pool("unit", [{"key": "sk-recover"}])

    for _ in range(3):
        key_pool.report_key_result("unit", "sk-recover", False, error_code=429)
    key_pool.report_key_result("unit", "sk-recover", True)

    snapshot = key_pool.pool_snapshot("unit")
    assert snapshot["entries"][0]["consecutive_429"] == 0


# ── Key IDs never expose raw key ───────────────────────────────────────────────

def test_snapshot_never_exposes_raw_keys():
    keys = [
        {"key": "sk-prod-secret-12345678"},
        {"key": "org-secret-key-abcdefgh"},
    ]
    key_pool.register_pool("prod", keys)

    text = str(key_pool.pool_snapshot("prod"))
    for k in keys:
        assert k["key"] not in text, f"Raw key {k['key']} leaked in snapshot"


def test_error_report_does_not_log_raw_key():
    key_pool.register_pool("unit", [{"key": "sk-very-long-secret-key-12345"}])
    key_pool.report_key_result("unit", "sk-very-long-secret-key-12345", False, error_code=429)
    # The fingerprint should only have last 4 chars
    entry = key_pool.pool_snapshot("unit")["entries"][0]
    key_id = entry["key_id"]
    assert "very-long-secret" not in key_id
    assert key_id.endswith(":2345")
