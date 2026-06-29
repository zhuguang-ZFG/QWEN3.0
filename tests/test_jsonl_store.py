import json
import logging

from observability.jsonl_store import append_jsonl_record, read_recent_jsonl_records


def test_append_jsonl_record_rotates_when_size_exceeded(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    logger = logging.getLogger("test_jsonl_store")

    for index in range(10):
        assert append_jsonl_record(
            path,
            {"index": index, "payload": "x" * 40},
            max_bytes=120,
            logger=logger,
        )

    # Rotation creates numbered backups; the most recent records remain readable.
    backups = list(tmp_path.glob("telemetry.jsonl.*"))
    assert backups
    recent = read_recent_jsonl_records(path, limit=5)
    assert [r["index"] for r in recent] == [5, 6, 7, 8, 9]


def test_append_jsonl_record_can_disable_size_trim(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    logger = logging.getLogger("test_jsonl_store")

    for index in range(5):
        assert append_jsonl_record(
            path,
            {"index": index, "payload": "x" * 40},
            max_bytes=0,
            logger=logger,
        )

    assert len(path.read_text(encoding="utf-8").splitlines()) == 5
    assert not list(tmp_path.glob("telemetry.jsonl.*"))


def test_read_recent_jsonl_records_includes_backups(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    logger = logging.getLogger("test_jsonl_store")

    # Force rotation after a few small records.
    for index in range(8):
        append_jsonl_record(
            path,
            {"index": index},
            max_bytes=60,
            logger=logger,
        )

    records = read_recent_jsonl_records(path, limit=5)
    indices = [r["index"] for r in records]
    assert indices == [3, 4, 5, 6, 7]


def test_read_recent_jsonl_records_returns_empty_for_missing_file(tmp_path):
    path = tmp_path / "missing.jsonl"
    assert read_recent_jsonl_records(path, limit=10) == []
