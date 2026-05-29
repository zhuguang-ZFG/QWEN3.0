"""Agent Contract System — inspired by Hermes Agent Orange Book patterns.

Defines what each agent can do, what evidence it must produce, and how
stages gate each other. LiMa-native implementation — no external deps.

Core concepts:
  1. AgentRole: named capability set with input/output contracts
  2. StageGate: evidence-gated transition between pipeline stages
  3. EvidenceRequirement: typed evidence needed to pass a gate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentRole(str, Enum):
    PLANNER = "planner"       # break goal into tasks, assess risk
    CODER = "coder"            # write/change code, run tests
    REVIEWER = "reviewer"      # review diffs, check security, score quality
    SHIPPER = "shipper"       # commit, push, create PR, deploy
    MONITOR = "monitor"        # watch CI, device status, health checks
    LEARNER = "learner"        # analyze outcomes, propose improvements


class Stage(str, Enum):
    PLAN = "plan"
    CODE = "code"
    TEST = "test"
    REVIEW = "review"
    SHIP = "ship"
    MONITOR = "monitor"
    LEARN = "learn"


@dataclass
class EvidenceRequirement:
    """What evidence must exist before advancing to the next stage."""
    evidence_type: str        # artifact type: plan.md, tests.json, review.md, etc.
    min_items: int = 1
    format: str = ""          # expected format hint
    required_fields: list[str] = field(default_factory=list)


@dataclass
class StageGate:
    """A gate between pipeline stages."""
    from_stage: Stage
    to_stage: Stage
    required_evidence: list[EvidenceRequirement] = field(default_factory=list)
    requires_approval: bool = False
    auto_pass_conditions: list[str] = field(default_factory=list)


@dataclass
class AgentContract:
    """What an agent role can do and what it must produce."""
    role: AgentRole
    allowed_tools: list[str] = field(default_factory=list)
    produces_evidence: list[str] = field(default_factory=list)  # evidence types
    requires_evidence: list[str] = field(default_factory=list)  # from prior stages
    max_runtime_sec: int = 300
    can_approve: bool = False


# ── Standard Pipeline ──

STANDARD_PIPELINE: list[StageGate] = [
    StageGate(
        Stage.PLAN, Stage.CODE,
        required_evidence=[
            EvidenceRequirement("plan.md", min_items=1, required_fields=["goal", "files", "risks"]),
            EvidenceRequirement("context.json", required_fields=["repo", "branch"]),
        ],
        requires_approval=True,
    ),
    StageGate(
        Stage.CODE, Stage.TEST,
        required_evidence=[
            EvidenceRequirement("diff.patch", min_items=1, required_fields=["changed_files"]),
            EvidenceRequirement("tests.json", required_fields=["command", "exit_code"]),
        ],
    ),
    StageGate(
        Stage.TEST, Stage.REVIEW,
        required_evidence=[
            EvidenceRequirement("tests.json", min_items=1, required_fields=["command", "exit_code", "duration_ms"]),
        ],
        auto_pass_conditions=["all_tests_pass"],
    ),
    StageGate(
        Stage.REVIEW, Stage.SHIP,
        required_evidence=[
            EvidenceRequirement("review.md", min_items=1, required_fields=["score", "risks", "verdict"]),
            EvidenceRequirement("diff.patch"),
        ],
        requires_approval=True,
    ),
    StageGate(
        Stage.SHIP, Stage.MONITOR,
        required_evidence=[
            EvidenceRequirement("ship.md", required_fields=["commit", "changed_files", "rollback_notes"]),
        ],
    ),
    StageGate(
        Stage.MONITOR, Stage.LEARN,
        required_evidence=[
            EvidenceRequirement("outcome", min_items=1, required_fields=["source", "outcome"]),
        ],
        auto_pass_conditions=["ci_passed", "no_alerts"],
    ),
]


# ── Agent Contracts ──

AGENT_CONTRACTS: dict[AgentRole, AgentContract] = {
    AgentRole.PLANNER: AgentContract(
        role=AgentRole.PLANNER,
        allowed_tools=["read_file", "list_directory", "glob_search", "search_repo", "search_memory",
                       "dev_search_docs", "dev_search_error", "github_search_code"],
        produces_evidence=["plan.md", "context.json", "risks.md"],
        requires_evidence=[],
        max_runtime_sec=180,
    ),
    AgentRole.CODER: AgentContract(
        role=AgentRole.CODER,
        allowed_tools=["read_file", "write_file", "glob_search",
                       "github_get_file_contents", "github_search_code"],
        produces_evidence=["diff.patch", "tests.json"],
        requires_evidence=["plan.md", "context.json"],
        max_runtime_sec=600,
    ),
    AgentRole.REVIEWER: AgentContract(
        role=AgentRole.REVIEWER,
        allowed_tools=["read_file", "git_diff", "git_log",
                       "github_list_workflow_runs", "github_list_check_runs"],
        produces_evidence=["review.md", "diff.patch"],
        requires_evidence=["tests.json", "diff.patch"],
        max_runtime_sec=300,
        can_approve=True,
    ),
    AgentRole.SHIPPER: AgentContract(
        role=AgentRole.SHIPPER,
        allowed_tools=["git_commit", "git_push", "github_create_branch",
                       "github_create_pull_request", "github_add_issue_comment"],
        produces_evidence=["ship.md", "diff.patch"],
        requires_evidence=["review.md", "tests.json"],
        max_runtime_sec=180,
    ),
    AgentRole.MONITOR: AgentContract(
        role=AgentRole.MONITOR,
        allowed_tools=["github_list_workflow_runs", "github_list_workflow_jobs",
                       "github_get_combined_status", "outcome_ledger_stats", "memory_stats"],
        produces_evidence=["outcome"],
        requires_evidence=["ship.md"],
        max_runtime_sec=60,
    ),
    AgentRole.LEARNER: AgentContract(
        role=AgentRole.LEARNER,
        allowed_tools=["search_memory", "outcome_ledger_stats", "memory_stats",
                       "github_search_issues", "source_stackexchange_search"],
        produces_evidence=["learned_pattern"],
        requires_evidence=["outcome"],
        max_runtime_sec=120,
    ),
}


def check_gate(gate: StageGate, evidence: dict[str, list]) -> tuple[bool, str]:
    """Check if evidence satisfies a stage gate.

    Returns (passed, reason).
    """
    for req in gate.required_evidence:
        items = evidence.get(req.evidence_type, [])
        if len(items) < req.min_items:
            return False, f"need {req.min_items} {req.evidence_type}, have {len(items)}"
        if req.required_fields:
            for item in items:
                missing = [f for f in req.required_fields if f not in item]
                if missing:
                    return False, f"{req.evidence_type} missing fields: {missing}"
    return True, "gate passed"


def get_contract(role: AgentRole) -> AgentContract:
    return AGENT_CONTRACTS.get(role, AgentContract(role=role))


def get_pipeline() -> list[StageGate]:
    return STANDARD_PIPELINE
