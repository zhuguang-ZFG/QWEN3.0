"""Tests for LiMa Task Prompt Contract v0.1."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_runtime.prompt_contract import (
    DEFAULT_OUTPUT,
    PromptContract,
    contract_to_dict,
    migrate_from_legacy,
    parse_prompt_contract,
    render_prompt_contract,
    resolve_prompt_contract,
)

GOLDEN_LEGACY = """## Context
(none)

## Task
fix routing bug

## Constraints
- no deploy
- test: pytest -q

## Verify
- pytest -q

## Output
Return needs_review with summary JSON: changed_files, tests_run, remaining_risks, review_status."""


class TestMigrateFromLegacy:
    def test_goal_maps_to_task_and_test_commands_to_verify(self):
        contract = migrate_from_legacy(
            "fix routing bug",
            constraints=["no deploy", "test: pytest -q"],
            test_commands=["pytest -q"],
            mode="patch",
        )
        rendered = render_prompt_contract(contract)
        assert rendered == GOLDEN_LEGACY

    def test_empty_goal_raises(self):
        with pytest.raises(ValueError, match="goal"):
            migrate_from_legacy("")


class TestParsePromptContract:
    def test_rejects_oversized_task(self):
        with pytest.raises(ValueError, match="task"):
            parse_prompt_contract({"task": "x" * 1001})

    def test_accepts_full_contract(self):
        contract = parse_prompt_contract(
            {
                "context": "repo is LiMa",
                "task": "add tests",
                "constraints": ["small diff"],
                "verify": ["pytest"],
                "output": "needs_review",
            }
        )
        assert contract.task == "add tests"
        assert contract.verify == ["pytest"]


class TestResolvePromptContract:
    def test_legacy_only(self):
        contract = resolve_prompt_contract(goal="review diff", mode="review")
        assert contract.task == "review diff"
        assert "diff review" in contract.output

    def test_explicit_overrides_task(self):
        contract = resolve_prompt_contract(
            goal="legacy goal",
            prompt_contract={"task": "explicit task", "context": "ctx"},
        )
        assert contract.task == "explicit task"
        assert contract.context == "ctx"

    def test_explicit_empty_constraints_keeps_empty(self):
        contract = resolve_prompt_contract(
            goal="goal",
            constraints=["keep me"],
            prompt_contract={"constraints": []},
        )
        assert contract.constraints == []


class TestRenderPromptContract:
    def test_golden_explicit_contract(self):
        contract = PromptContract(
            context="LiMa server repo",
            task="Wire prompt contract",
            constraints=["backward compatible"],
            verify=["python -m pytest tests/test_prompt_contract.py -q"],
            output=DEFAULT_OUTPUT,
        )
        rendered = render_prompt_contract(contract)
        assert "## Context" in rendered
        assert "LiMa server repo" in rendered
        assert "## Task" in rendered
        assert "Wire prompt contract" in rendered
        assert "## Verify" in rendered
        assert "pytest" in rendered
        assert "## Output" in rendered

    def test_contract_to_dict_round_trip(self):
        contract = migrate_from_legacy("goal", mode="plan")
        again = parse_prompt_contract(contract_to_dict(contract))
        assert again.task == contract.task
        assert again.verify == contract.verify
