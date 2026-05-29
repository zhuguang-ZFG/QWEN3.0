"""Resume contract for reconstructing task state from stored run records.

Answers whether a task can resume and suggests the next operator action. All
resume state serialization is sanitized.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_runtime.contract import AgentRunResult, AgentRunStatus, AgentTask, redact
from agent_runtime.store import AgentRunStore


@dataclass
class ResumeState:
    task_id: str
    status: AgentRunStatus
    completed_steps: list[str] = field(default_factory=list)
    blocked_steps: list[str] = field(default_factory=list)
    failed_step: str = ""
    next_action: str = ""
    can_resume: bool = False
    resume_note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": redact(self.task_id),
            "status": self.status.value,
            "completed_steps": [redact(step) for step in self.completed_steps],
            "blocked_steps": [redact(step) for step in self.blocked_steps],
            "failed_step": redact(self.failed_step),
            "next_action": redact(self.next_action),
            "can_resume": self.can_resume,
            "resume_note": redact(self.resume_note),
        }


def build_resume_state(task: AgentTask, result: AgentRunResult) -> ResumeState:
    completed = [step.step_id for step in result.steps if step.ok and not step.blocked]
    blocked = [step.step_id for step in result.steps if step.blocked]
    failed = next(
        (step.step_id for step in result.steps if not step.ok and not step.blocked),
        "",
    )

    next_action = "review_results"
    can_resume = False
    if blocked:
        next_action = "approve_blocked_steps"
        can_resume = True
    elif result.status == AgentRunStatus.FAILED or failed:
        next_action = "fix_error_and_retry"
        can_resume = True
    elif result.status == AgentRunStatus.COMPLETED:
        next_action = "done"

    note = ""
    if failed:
        note = f"step '{failed}' failed; check output and retry"
    elif blocked:
        note = f"{len(blocked)} step(s) blocked: {', '.join(blocked[:3])}"

    return ResumeState(
        task_id=task.task_id,
        status=result.status,
        completed_steps=completed,
        blocked_steps=blocked,
        failed_step=failed,
        next_action=next_action,
        can_resume=can_resume,
        resume_note=note,
    )


def resume_task(task_id: str, store: AgentRunStore) -> ResumeState | None:
    task = store.get_task(task_id)
    result = store.get_result(task_id)
    if not task or not result:
        return None
    return build_resume_state(task, result)


def format_resume_summary(state: ResumeState) -> str:
    data = state.to_dict()
    lines = [
        f"Task: {data['task_id']}",
        f"Status: {data['status']}",
        f"Completed: {len(state.completed_steps)} steps",
        f"Blocked: {len(state.blocked_steps)} steps",
        f"Next action: {data['next_action']}",
    ]
    if data["resume_note"]:
        lines.append(f"Note: {data['resume_note']}")
    return "\n".join(lines)
