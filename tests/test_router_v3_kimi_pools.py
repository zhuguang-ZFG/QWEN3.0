"""Regression: Kimi local-proxy backends stay out of default routing pools."""

import router_v3


def test_code_medium_pool_excludes_kimi_family():
    medium = router_v3.POOLS["code"]["medium"]
    for name in ("kimi", "kimi_thinking", "kimi_search"):
        assert name not in medium


def test_scnet_ds_pro_remains_code_strong():
    assert "scnet_ds_pro" in router_v3.POOLS["code"]["strong"]
