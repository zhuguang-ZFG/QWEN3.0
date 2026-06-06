"""Tests for M4: developer skills — investigate, review, ship, learn."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from developer_skills import SkillResult
from developer_skills.investigate import investigate
from developer_skills.learn import learn
from developer_skills.review import review
from developer_skills.ship import ship


class TestInvestigate:
    def test_investigate_existing_file(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("def hello():\n    return 'world'\n")
        result = investigate(str(p))
        assert result.ok is True
        assert result.skill == "investigate"
        assert len(result.details) > 0
        assert any("test.py" in d for d in result.details)

    def test_investigate_nonexistent_file(self):
        result = investigate("nonexistent_file_xyz.py")
        assert result.ok is True
        assert "not a file" in result.summary.lower() or "query" in " ".join(result.details).lower()


class TestReview:
    def test_review_clean_file(self, tmp_path):
        p = tmp_path / "clean.py"
        p.write_text("def hello():\n    return 42\n")
        result = review(str(p))
        assert result.ok is True
        assert result.skill == "review"

    def test_review_bare_except(self, tmp_path):
        p = tmp_path / "bad.py"
        p.write_text("try:\n    pass\nexcept Exception:\n    pass\n")
        result = review(str(p))
        assert result.ok is True
        assert any("[error]" in d for d in result.details)

    def test_review_large_file(self, tmp_path):
        p = tmp_path / "big.py"
        p.write_text("\n".join(f"def func_{i}(): pass" for i in range(350)))
        result = review(str(p))
        assert result.ok is True
        assert any("300 lines" in d for d in result.details)

    def test_review_directory(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        result = review(str(tmp_path))
        assert result.ok is True

    def test_review_nonexistent(self):
        result = review("/nonexistent/path/xyz")
        assert result.ok is False


class TestShip:
    def test_ship_clean_tree(self, tmp_path):
        os.chdir(tmp_path)
        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], capture_output=True)
        result = ship()
        assert result.ok is True
        assert "clean" in result.summary.lower()

    def test_ship_with_changes(self, tmp_path):
        os.chdir(tmp_path)
        subprocess.run(["git", "init"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], capture_output=True)
        (tmp_path / "test.txt").write_text("hello")
        subprocess.run(["git", "add", "."], capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], capture_output=True)

        (tmp_path / "test.txt").write_text("hello world")
        result = ship("update test.txt", push=False, stage_all=True)
        assert result.ok is True
        assert "shipped" in result.summary.lower() or "commit" in " ".join(result.details).lower()


class TestLearn:
    def test_learn_observation(self):
        result = learn("groq llama70b is fast for Python")
        assert result.ok is True
        assert result.skill == "learn"
        assert len(result.details) > 0

    def test_learn_empty(self):
        result = learn("")
        assert result.ok is False

    def test_learn_skill_key(self):
        result = learn("scnet qwen is great for code")
        assert result.ok is True
        assert any("scnet" in d for d in result.details)
