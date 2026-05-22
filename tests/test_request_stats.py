import server


def test_elapsed_ms_clamps_and_reports_real_duration(monkeypatch):
    monkeypatch.setattr(server.time, "time", lambda: 12.5)
    assert server._elapsed_ms(10.0) == 2500

    monkeypatch.setattr(server.time, "time", lambda: 9.0)
    assert server._elapsed_ms(10.0) == 0
