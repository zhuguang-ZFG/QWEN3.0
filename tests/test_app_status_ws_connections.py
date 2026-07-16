"""Status WebSocket connection limits release slots deterministically."""

import app_status_ws_connections as connections


def test_status_ws_connection_limit_and_release() -> None:
    connections.reset()
    assert connections.try_acquire("a-1", "dev-1", max_concurrent=1) is True
    assert connections.try_acquire("a-1", "dev-1", max_concurrent=1) is False
    connections.release("a-1", "dev-1")
    assert connections.count("a-1", "dev-1") == 0
    assert connections.try_acquire("a-1", "dev-1", max_concurrent=1) is True
    connections.reset()
