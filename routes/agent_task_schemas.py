"""Pydantic request bodies for agent task routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TaskCreateBody(BaseModel):
    repo: str
    branch: str = "main"
    goal: str
    constraints: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    max_runtime_sec: int = 300
    mode: Literal["plan", "patch", "test", "review"] = "patch"
    patch_files: list[dict] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)


class WorkerSmokeTaskBody(BaseModel):
    repo: str
    branch: str = "main"
    kind: Literal["review", "patch_readme"] = "review"


class TaskResultBody(BaseModel):
    task_id: str
    status: Literal[
        "accepted", "claimed", "running", "needs_review", "approved",
        "rejected", "applied", "succeeded", "failed", "blocked",
        "cancel_requested", "cancelled", "quarantined",
    ]
    summary: str
    changed_files: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    test_results: list[dict] = Field(default_factory=list)
    diff_preview: str = ""
    artifacts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_action: str = ""
    backend: str = ""
    latency_ms: int = 0


class ClaimBody(BaseModel):
    worker_id: str
    lease_sec: int = Field(default=300, ge=1, le=3600)


class ReviewBody(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer: str = "human"
    note: str = ""


class PromoteBody(BaseModel):
    eval_passed: bool = False
    manual_flag: bool = False
    mastery_evidence_refs: list[str] = Field(default_factory=list)
