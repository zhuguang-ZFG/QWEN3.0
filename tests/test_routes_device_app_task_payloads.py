"""Tests for routes/device_app_task_payloads.py helpers."""

from __future__ import annotations

import json


from routes.device_app_task_payloads import (
    merge_task_lists,
    snapshot_payload,
    task_row_payload,
    task_summary_payload,
)


class TestTaskRowPayload:
    def test_maps_fields_and_extracts_request_id(self):
        params = {"requestId": "req-1", "constraints": {"max_len": 100}}
        row = {
            "id": "task-1",
            "device_id": "dev-1",
            "intent": "chat",
            "params": json.dumps(params),
            "source": "voice",
            "status": "pending",
            "progress": 0,
            "error_msg": "",
            "member_id": "mem-1",
            "created_at": "2024-01-01T00:00:00Z",
            "started_at": "",
            "completed_at": "",
        }
        payload = task_row_payload(row)
        assert payload["taskId"] == "task-1"
        assert payload["requestId"] == "req-1"
        assert json.loads(payload["constraintsJson"]) == {"max_len": 100}
        assert payload["params"]["requestId"] == "req-1"

    def test_request_id_fallback(self):
        row = {
            "id": "task-2",
            "device_id": "dev-1",
            "intent": "chat",
            "params": json.dumps({"request_id": "req-2"}),
            "source": "voice",
            "status": "pending",
            "progress": 0,
            "error_msg": "",
            "member_id": "",
            "created_at": "",
            "started_at": "",
            "completed_at": "",
        }
        assert task_row_payload(row)["requestId"] == "req-2"


class TestTaskSummaryPayload:
    def test_defaults(self):
        assert task_summary_payload({}) == {
            "taskId": "",
            "deviceId": "",
            "capability": "",
            "requestId": "",
            "source": "",
            "status": "unknown",
        }


class TestSnapshotPayload:
    def test_extracts_task_params(self):
        snapshot = {
            "task": {
                "task_id": "t1",
                "device_id": "d1",
                "capability": "chat",
                "request_id": "r1",
                "params": {"x": 1},
                "constraints": {"y": 2},
                "source": "api",
            },
            "status": "running",
            "retry_count": 2,
            "events": [{"at": 1}],
        }
        payload = snapshot_payload(snapshot)
        assert payload["taskId"] == "t1"
        assert payload["params"] == {"x": 1}
        assert json.loads(payload["constraintsJson"]) == {"y": 2}
        assert payload["retryCount"] == 2

    def test_missing_task_defaults(self):
        payload = snapshot_payload({"status": "done"})
        assert payload["taskId"] == ""
        assert payload["params"] == {}
        assert payload["events"] == []


class TestMergeTaskLists:
    def test_prefers_db_tasks_and_dedups(self):
        db = [{"taskId": "t1", "source": "db"}]
        store = [{"task_id": "t1", "source": "store"}]
        result = merge_task_lists(db, store, 10, lambda _id: None)
        assert len(result) == 1
        assert result[0]["source"] == "db"

    def test_includes_store_tasks_via_snapshot(self):
        db = []
        store = [{"task_id": "t2", "capability": "chat", "source": "store"}]

        def snapshot_fn(task_id: str):
            return {"task": {"task_id": task_id}, "status": "pending"}

        result = merge_task_lists(db, store, 10, snapshot_fn)
        assert len(result) == 1
        assert result[0]["taskId"] == "t2"

    def test_respects_limit(self):
        db = [{"taskId": f"t{i}"} for i in range(5)]
        result = merge_task_lists(db, [], 3, lambda _id: None)
        assert len(result) == 3

    def test_ignores_store_tasks_without_id(self):
        result = merge_task_lists([], [{"task_id": ""}, {"task_id": "t1"}], 10, lambda _id: None)
        assert len(result) == 1
