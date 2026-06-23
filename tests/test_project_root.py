"""Tests for context_pipeline/_project_root.py — project root detection."""

from unittest.mock import patch

from context_pipeline._project_root import _detect_project_root


class TestDetectProjectRoot:
    def test_env_root_priority(self):
        with patch.dict("os.environ", {"LIMA_PROJECT_ROOT": "."}):
            assert _detect_project_root() == "."

    def test_env_root_ignored_if_not_dir(self):
        with patch.dict("os.environ", {"LIMA_PROJECT_ROOT": "/nonexistent/path"}):
            with patch("os.path.isdir", return_value=False):
                result = _detect_project_root()
                assert isinstance(result, str)

    def test_fallback_to_cwd(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("os.getcwd", return_value="/fake/cwd"):
                with patch("os.path.isdir", return_value=False):
                    assert _detect_project_root() == "/fake/cwd"
