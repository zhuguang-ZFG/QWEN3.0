"""Regression: Kimi local-proxy backends in code routing pools."""

import router_v3


def test_code_medium_pool_includes_kimi_family():
    medium = router_v3.POOLS["code"]["medium"]
    for name in ("kimi", "kimi_thinking", "kimi_search"):
        assert name in medium


def test_scnet_ds_pro_remains_code_strong():
    assert "scnet_ds_pro" in router_v3.POOLS["code"]["strong"]
