import logging

import route_post_process


def test_warn_helper_logs_stage(caplog):
    with caplog.at_level(logging.WARNING):
        route_post_process._warn("narrative", RuntimeError("boom"))
    assert "post-route narrative failed" in caplog.text


def test_post_route_import_error_is_silent():
    route_post_process.apply_post_route_integrations(
        final_backend="unit_backend",
        answer="ok",
        backends=["unit_backend"],
        messages_injected=[],
        messages=[],
        req_type="chat",
        scenario="chat",
        ms=1,
    )
