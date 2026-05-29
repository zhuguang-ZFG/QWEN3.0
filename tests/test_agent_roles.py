"""Tests for agent_roles module."""

import pytest
from agent_roles import Role, ROLES, get_role


EXPECTED_ROLES = ["planner", "coder", "reviewer", "tester", "security", "ops", "memory_curator"]


def request_patch_mode(role: Role) -> bool:
    """Helper: returns True only if role is allowed to use patch mode."""
    return role.can_modify_code


class TestRoleRegistry:
    def test_all_seven_roles_exist(self):
        assert set(ROLES.keys()) == set(EXPECTED_ROLES)

    def test_get_role_returns_correct_instance(self):
        for name in EXPECTED_ROLES:
            role = get_role(name)
            assert role.name == name

    def test_get_role_unknown_raises(self):
        with pytest.raises(KeyError):
            get_role("nonexistent")


class TestCodeModification:
    def test_only_coder_can_modify_code(self):
        for name, role in ROLES.items():
            if name == "coder":
                assert role.can_modify_code is True
            else:
                assert role.can_modify_code is False

    def test_non_coder_cannot_request_patch_mode(self):
        for name, role in ROLES.items():
            if name != "coder":
                assert request_patch_mode(role) is False

    def test_coder_can_request_patch_mode(self):
        assert request_patch_mode(get_role("coder")) is True


class TestEvidenceOnlyRoles:
    """reviewer, tester, security return evidence only (no code modification)."""

    @pytest.mark.parametrize("role_name", ["reviewer", "tester", "security"])
    def test_evidence_roles_cannot_modify(self, role_name):
        role = get_role(role_name)
        assert role.can_modify_code is False
        assert request_patch_mode(role) is False


class TestRoleProperties:
    def test_ops_properties(self):
        ops = get_role("ops")
        assert ops.runs_on == "server"
        assert ops.can_modify_code is False
        assert "deploy_plan" in ops.output_fields

    def test_planner_properties(self):
        p = get_role("planner")
        assert p.runs_on == "server"
        assert p.output_fields == ("plan", "risks", "phases")

    def test_memory_curator_properties(self):
        mc = get_role("memory_curator")
        assert mc.runs_on == "server"
        assert "memories_updated" in mc.output_fields
        assert "memories_expired" in mc.output_fields
