import json
import logging

from observability.jsonl_store import append_jsonl_record


def test_append_jsonl_record_trims_to_recent_lines(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    logger = logging.getLogger("test_jsonl_store")

    for index in range(10):
        assert append_jsonl_record(
            path,
            {"index": index, "payload": "x" * 40},
            keep_lines=3,
            max_bytes=120,
            logger=logger,
        )

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [item["index"] for item in records] == [7, 8, 9]


def test_append_jsonl_record_can_disable_size_trim(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    logger = logging.getLogger("test_jsonl_store")

    for index in range(5):
        assert append_jsonl_record(
            path,
            {"index": index, "payload": "x" * 40},
            keep_lines=1,
            max_bytes=0,
            logger=logger,
        )

    assert len(path.read_text(encoding="utf-8").splitlines()) == 5
