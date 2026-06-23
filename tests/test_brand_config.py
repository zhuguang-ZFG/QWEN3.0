"""Tests for brand_config.py — brand defaults."""

import importlib

import brand_config


class TestBrandDefaults:
    def test_public_model_name(self):
        assert brand_config.PUBLIC_MODEL_NAME == "LiMa"

    def test_user_agent(self):
        assert "LiMa" in brand_config.USER_AGENT

    def test_capability_bullets(self):
        assert "realtime" in brand_config.CAPABILITY_BULLETS_CN
        assert "programming" in brand_config.CAPABILITY_BULLETS_EN

    def test_env_override(self):
        from config.settings import BRAND

        original = BRAND.public_model_name
        try:
            BRAND.public_model_name = "TestModel"
            importlib.reload(brand_config)
            assert brand_config.PUBLIC_MODEL_NAME == "TestModel"
        finally:
            BRAND.public_model_name = original
            importlib.reload(brand_config)
            assert brand_config.PUBLIC_MODEL_NAME == original
