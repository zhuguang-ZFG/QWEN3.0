"""Tests for agent task contract validation."""

import pytest

from agent_contracts.task_contract import AgentTaskRequest, AgentTaskResult


class TestAgentTaskRequest:
    """Tests for AgentTaskRequest dataclass."""

    def _valid_request(self, **overrides) -> AgentTaskRequest:
        defaults = dict(
            task_id="task-001",
            repo="D:/GIT",
            branch="main",
            goal="Fix the bug",
            mode="patch",
        )
        defaults.update(overrides)
        return AgentTaskRequest(**defaults)

    def test_valid_request_passes_validation(self):
        req = self._valid_request()
        req.validate()  # should not raise

    def test_all_modes_are_valid(self):
        for mode in ("plan", "patch", "test", "review"):
            req = self._valid_request(mode=mode)
            req.validate()

    def test_invalid_mode_raises(self):
        req = self._valid_request()
        req.mode = "deploy"
        with pytest.raises(ValueError, match="Invalid mode"):
            req.validate()

    def test_empty_task_id_raises(self):
        req = self._valid_request(task_id="")
        with pytest.raises(ValueError, match="task_id"):
            req.validate()

    def test_empty_goal_raises(self):
        req = self._valid_request(goal="")
        with pytest.raises(ValueError, match="goal"):
            req.validate()

    def test_negative_runtime_raises(self):
        req = self._valid_request(max_runtime_sec=-1)
        with pytest.raises(ValueError, match="max_runtime_sec"):
            req.validate()

    def test_required_fields_present(self):
        req = self._valid_request()
        for attr in ("task_id", "repo", "branch", "goal", "mode"):
            assert hasattr(req, attr)

    def test_accepts_worker_lifecycle_metadata(self):
        req = self._valid_request(
            repo="D:/GIT/deepcode-cli",
            goal="review diff",
            allowed_tools=["git_diff"],
            max_runtime_sec=300,
            mode="review",
            worker_id="worker-local",
            lease_expires_at=123.0,
            cancel_requested=False,
            failure_count=0,
        )
        req.validate()
        assert req.worker_id == "worker-local"
        assert req.lease_expires_at == 123.0
        assert req.cancel_requested is False
        assert req.failure_count == 0

    def test_negative_failure_count_raises(self):
        req = self._valid_request(failure_count=-1)
        with pytest.raises(ValueError, match="failure_count"):
            req.validate()

    def test_accepts_patch_files_and_test_commands(self):
        req = self._valid_request(
            allowed_tools=["write", "git_diff", "test"],
            patch_files=[{"file_path": "README.md", "content": "# Smoke\n"}],
            test_commands=["node test.js"],
        )
        req.validate()
        assert req.patch_files == [
            {"file_path": "README.md", "content": "# Smoke\n"}
        ]
        assert req.test_commands == ["node test.js"]


class TestAgentTaskResult:
    """Tests for AgentTaskResult dataclass."""

    def _valid_result(self, **overrides) -> AgentTaskResult:
        defaults = dict(
            task_id="task-001",
            status="succeeded",
            summary="All tests pass",
        )
        defaults.update(overrides)
        return AgentTaskResult(**defaults)

    def test_valid_result_passes_validation(self):
        res = self._valid_result()
        res.validate()

    def test_all_statuses_are_valid(self):
        for status in (
            "accepted", "claimed", "running", "needs_review",
            "approved", "rejected", "applied", "succeeded",
            "failed", "blocked", "cancel_requested",
            "cancelled", "quarantined",
        ):
            res = self._valid_result(status=status)
            res.validate()

    def test_invalid_status_raises(self):
        res = self._valid_result()
        res.status = "done"
        with pytest.raises(ValueError, match="Invalid status"):
            res.validate()

    def test_empty_task_id_raises(self):
        res = self._valid_result(task_id="")
        with pytest.raises(ValueError, match="task_id"):
            res.validate()

    def test_required_fields_present(self):
        res = self._valid_result()
        for attr in (
            "task_id", "status", "summary",
            "changed_files", "test_commands", "test_results",
            "diff_preview", "artifacts", "risks", "next_action",
        ):
            assert hasattr(res, attr)
