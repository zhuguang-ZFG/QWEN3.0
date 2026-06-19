"""Table existence + indices tests."""

from tests.xiaozhi_schema.conftest import ALL_TABLES, _table_names


def test_all_10_tables_exist(db):
    names = _table_names(db)
    for t in ALL_TABLES:
        assert t in names, f"table {t} missing from schema"
    assert len([n for n in names if n in ALL_TABLES]) == 10


def test_indices_exist(db):
    """Verify key indices are present."""
    indices = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
    expected = {
        "idx_v2_account_phone",
        "idx_v2_account_wechat",
        "idx_v2_device_sn",
        "idx_v2_device_status",
        "idx_v2_binding_device",
        "idx_v2_binding_account",
        "idx_v2_member_device",
        "idx_v2_member_account",
        "idx_v2_voiceprint_member",
        "idx_v2_voiceprint_device",
        "idx_v2_task_device",
        "idx_v2_task_status",
        "idx_v2_task_created",
        "idx_v2_transfer_device",
        "idx_v2_transfer_to",
        "idx_v2_transfer_status",
        "idx_v2_rma_device",
        "idx_v2_rma_status",
        "idx_v2_supply_device",
        "idx_v2_selfcheck_device",
        "idx_v2_selfcheck_result",
        "idx_v2_selfcheck_created",
    }
    missing = expected - indices
    assert not missing, f"missing indices: {missing}"
