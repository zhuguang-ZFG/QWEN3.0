"""Tests for brand_config.py — brand defaults."""

from unittest.mock import patch


class TestBrandDefaults:
    def test_public_model_name(self):
        import brand_config
        assert brand_config.PUBLIC_MODEL_NAME == "LiMa"

    def test_user_agent(self):
        import brand_config
        assert "LiMa" in brand_config.USER_AGENT

    def test_capability_bullets(self):
        import brand_config
        assert "realtime" in brand_config.CAPABILITY_BULLETS_CN
        assert "programming" in brand_config.CAPABILITY_BULLETS_EN

    def test_env_override(self):
        with patch.dict("os.environ", {"PUBLIC_MODEL_NAME": "TestModel"}):
            import importlib
            import brand_config

            importlib.reload(brand_config)
            assert brand_config.PUBLIC_MODEL_NAME == "TestModel"
