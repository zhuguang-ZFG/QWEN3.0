"""Tests for esp32s_adapter protocol conversion."""


from esp32s_adapter.protocol import edge_c_to_lima_event, generate_route_policy, lima_to_edge_c_task


class TestRoutePolicy:
    def test_control_capability(self):
        policy = generate_route_policy("home")
        assert policy["route_role"] == "device_control"
        assert policy["model_required"] is False
        assert policy["primary_strategy"] == "deterministic"
        assert policy["artifact_required"] == "none"

    def test_run_path_capability(self):
        policy = generate_route_policy("run_path")
        assert policy["route_role"] == "device_write"
        assert policy["primary_strategy"] == "provided_path"

    def test_unknown_capability(self):
        policy = generate_route_policy("unknown_cap")
        assert policy["route_role"] == "device_unknown"
        assert policy["primary_strategy"] == "planner_required"


class TestLimaToEdgeC:
    def test_home_task_minimal(self):
        lima_task = {
            "type": "task_dispatch",
            "device_id": "dev_001",
            "task_id": "t1",
            "capability": "home",
            "params": {},
        }
        edge_c = lima_to_edge_c_task(lima_task)
        assert edge_c["type"] == "motion_task"
        assert edge_c["device_id"] == "dev_001"
        assert edge_c["task_id"] == "t1"
        assert edge_c["capability"] == "home"
        assert edge_c["source"] == "client"
        assert "route_policy" in edge_c
        assert edge_c["route_policy"]["route_role"] == "device_control"

    def test_run_path_with_params(self):
        lima_task = {
            "type": "task_dispatch",
            "device_id": "dev_002",
            "task_id": "t2",
            "capability": "run_path",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}], "feed": 500.0},
            "request_id": "req_123",
        }
        edge_c = lima_to_edge_c_task(lima_task)
        assert edge_c["capability"] == "run_path"
        assert edge_c["params"]["path"] == [{"x": 0, "y": 0, "z": 0}]
        assert edge_c["params"]["feed"] == 500.0
        assert edge_c["request_id"] == "req_123"
        assert edge_c["route_policy"]["route_role"] == "device_write"

    def test_preserves_trace_id(self):
        lima_task = {
            "type": "task_dispatch",
            "device_id": "dev_003",
            "task_id": "t3",
            "capability": "pause",
            "params": {},
            "trace_id": "trace_abc",
        }
        edge_c = lima_to_edge_c_task(lima_task)
        assert edge_c["trace_id"] == "trace_abc"


class TestEdgeCToLima:
    def test_running_event_minimal(self):
        edge_c_event = {
            "session_id": "sess_001",
            "type": "motion_event",
            "task_id": "t1",
            "phase": "running",
            "device_id": "dev_001",
        }
        lima_event = edge_c_to_lima_event(edge_c_event)
        assert lima_event["type"] == "motion_event"
        assert lima_event["device_id"] == "dev_001"
        assert lima_event["task_id"] == "t1"
        assert lima_event["phase"] == "running"
        assert "session_id" not in lima_event

    def test_progress_event(self):
        edge_c_event = {
            "session_id": "sess_002",
            "type": "motion_event",
            "task_id": "t2",
            "phase": "progress",
            "device_id": "dev_002",
            "progress": {"done_segments": 5, "total_segments": 10, "percent": 50},
        }
        lima_event = edge_c_to_lima_event(edge_c_event)
        assert lima_event["phase"] == "progress"
        assert lima_event["progress"]["done_segments"] == 5
        assert lima_event["progress"]["total_segments"] == 10
        assert lima_event["progress"]["percent"] == 50

    def test_failed_event_with_error(self):
        edge_c_event = {
            "session_id": "sess_003",
            "type": "motion_event",
            "task_id": "t3",
            "phase": "failed",
            "device_id": "dev_003",
            "error_code": "E_LIMIT",
            "error_message": "Hit limit switch",
        }
        lima_event = edge_c_to_lima_event(edge_c_event)
        assert lima_event["phase"] == "failed"
        assert lima_event["error"]["code"] == "E_LIMIT"
        assert lima_event["error"]["reason"] == "Hit limit switch"

    def test_done_event(self):
        edge_c_event = {
            "session_id": "sess_004",
            "type": "motion_event",
            "task_id": "t4",
            "phase": "done",
            "device_id": "dev_004",
            "request_id": "req_456",
        }
        lima_event = edge_c_to_lima_event(edge_c_event)
        assert lima_event["phase"] == "done"
        assert lima_event["request_id"] == "req_456"


class TestRoundTrip:
    def test_home_task_roundtrip_preserves_ids(self):
        lima_task = {
            "type": "task_dispatch",
            "device_id": "dev_rt",
            "task_id": "t_rt",
            "capability": "home",
            "params": {},
            "request_id": "req_rt",
        }
        edge_c = lima_to_edge_c_task(lima_task)
        assert edge_c["device_id"] == "dev_rt"
        assert edge_c["task_id"] == "t_rt"
        assert edge_c["request_id"] == "req_rt"

        edge_c_event = {
            "session_id": "sess_rt",
            "type": "motion_event",
            "task_id": edge_c["task_id"],
            "phase": "done",
            "device_id": edge_c["device_id"],
            "request_id": edge_c["request_id"],
        }
        lima_event = edge_c_to_lima_event(edge_c_event)
        assert lima_event["device_id"] == "dev_rt"
        assert lima_event["task_id"] == "t_rt"
        assert lima_event["request_id"] == "req_rt"
