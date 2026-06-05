"""x_lima_meta context_injection attachment."""

from __future__ import annotations

from routes.chat_support import attach_lima_meta


def test_attach_lima_meta_includes_context_injection():
    resp = {"id": "c1", "choices": []}
    attach_lima_meta(
        resp,
        memory_meta={"checked": True, "applied": False},
        injection_meta={"summary": "retrieval=10c", "skills": ["dir:code"]},
    )
    assert resp["x_lima_meta"]["memory_recall"]["checked"] is True
    assert resp["x_lima_meta"]["context_injection"]["summary"] == "retrieval=10c"
