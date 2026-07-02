import time


import server
import routes.request_tracking as request_tracking


def test_elapsed_ms_clamps_and_reports_real_duration(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 12.5)
    assert server._elapsed_ms(10.0) == 2500

    monkeypatch.setattr(time, "time", lambda: 9.0)
    assert server._elapsed_ms(10.0) == 0


def test_record_request_looks_up_country_before_stats_lock(monkeypatch):
    observed_locks = []

    def record_location(_ip):
        observed_locks.append(server._stats_lock.locked())
        return "test-country"

    monkeypatch.setattr(request_tracking, "get_ip_location", record_location)
    monkeypatch.setattr(
        request_tracking,
        "_stats",
        {
            "total_requests": 0,
            "backend_calls": {},
            "intent_distribution": {},
            "recent_logs": [],
        },
    )

    server._record_request(
        "query",
        "backend",
        "chat",
        7,
        client_ip="203.0.113.7",
    )

    assert observed_locks == [False]
    assert request_tracking._stats["recent_logs"][-1]["country"] == "test-country"
