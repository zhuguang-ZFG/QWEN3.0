"""Learning loop package — feeds agent task outcomes back into memory, prompt,
routing, and eval systems.

All promotions are evidence-gated. Nothing changes routing behavior
automatically — every learned pattern must pass eval before adoption.
"""

from __future__ import annotations

from .eval_channel import get_eval_candidates
from .ingest import ingest_from_agent_task_result, ingest_task_outcome
from .models import TaskOutcome
from .prompt_channel import get_prompt_profile_stats

__all__ = [
    "TaskOutcome",
    "get_eval_candidates",
    "get_prompt_profile_stats",
    "ingest_from_agent_task_result",
    "ingest_task_outcome",
]
