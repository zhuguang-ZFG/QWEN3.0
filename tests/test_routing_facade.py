"""routing_facade gradual smart_router migration helpers."""

from __future__ import annotations

import routing_facade


def test_router_status_payload_shape():
    from routing_constants import PUBLIC_MODEL_NAME, ROUTE

    payload = routing_facade.router_status_payload()
    assert payload["routing_entry"] == "routing_engine.route"
    assert isinstance(payload.get("backends"), list)
    assert payload["route_table"] is ROUTE
    assert payload["public_model"] == PUBLIC_MODEL_NAME
    assert payload["route_table"]["unknown"] == "longcat_chat"


def test_routing_facade_module_has_no_smart_router_import():
    import inspect

    source = inspect.getsource(routing_facade)
    assert "import smart_router" not in source


def test_ide_coder_pool_uses_evidence(monkeypatch):
    import coding_pool_admission as admission

    monkeypatch.setattr(
        admission,
        "tier_pool_from_evidence",
        lambda tier, pool: ["promoted"] + list(pool),
    )

    pool = routing_facade.ide_coder_pool()
    assert pool and pool[0] == "promoted"
