"""Agent run queue datatypes."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from agent_runtime.contract import AgentTask


class QueueStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class AgentRunRequest:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task: AgentTask | None = None
    task_id: str = ""
    goal: str = ""
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    status: QueueStatus = QueueStatus.PENDING

    def __post_init__(self) -> None:
        if self.task:
            self.task_id = self.task.task_id
            self.goal = self.task.goal


@dataclass
class AgentRunLease:
    request_id: str
    worker_id: str
    claimed_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    lease_sec: float = 300.0

    def __post_init__(self) -> None:
        if self.expires_at <= 0:
            self.expires_at = self.claimed_at + self.lease_sec

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
