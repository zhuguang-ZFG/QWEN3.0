import asyncio
import pytest

import server


@pytest.mark.skip(reason="quality_gate removed in Phase 2 - device-first refactor (2026-06-12)")
def test_try_backend_forwards_full_messages(monkeypatch):
    pass
