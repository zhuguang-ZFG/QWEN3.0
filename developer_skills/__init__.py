"""Developer skills — structured developer workflow commands.

Provides /investigate, /review, /ship, /learn commands accessible via
Telegram and admin API. Uses agent_runtime for execution and code_context
for analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillResult:
    ok: bool
    skill: str
    summary: str
    details: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


from developer_skills.investigate import investigate
from developer_skills.review import review
from developer_skills.ship import ship
from developer_skills.learn import learn

__all__ = ["investigate", "review", "ship", "learn", "SkillResult"]
