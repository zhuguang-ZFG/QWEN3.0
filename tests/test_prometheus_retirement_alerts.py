"""Sanity checks for retirement alert rules (no baseline noise)."""

from pathlib import Path


def test_retirement_alerts_are_event_driven_not_inventory():
    text = Path("deploy/prometheus/backend_retirement_alerts.yml").read_text(encoding="utf-8")

    assert "LiMaBackendRetired:" not in text
    assert "LiMaBackendRetiredCountHigh" not in text
    assert "lima_backend_retired ==" not in text
    assert "lima_backend_retired_count > 0" not in text
    assert "increase(lima_backend_retirement_events_total" in text
    assert "delta(lima_backend_retired_count" in text
    assert "sum(increase(lima_backend_retirement_events_total" in text
