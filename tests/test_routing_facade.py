"""routing_facade gradual smart_router migration helpers."""

from __future__ import annotations

import routing_facade


def test_router_status_payload_shape():
    payload = routing_facade.router_status_payload()
    assert payload["routing_entry"] == "routing_engine.route"
    assert isinstance(payload.get("backends"), list)
    assert isinstance(payload.get("route_table"), dict)


def test_ide_coder_pool_uses_evidence(monkeypatch):
    import coding_pool_admission as admission

    monkeypatch.setattr(
        admission,
        "tier_pool_from_evidence",
        lambda tier, pool: ["promoted"] + list(pool),
    )

    pool = routing_facade.ide_coder_pool()
    assert pool and pool[0] == "promoted"
