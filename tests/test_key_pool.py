import key_pool


def setup_function():
    key_pool.clear_pools()


def teardown_function():
    key_pool.clear_pools()


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
