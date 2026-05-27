"""Learn command: persist observations to the L3 routing skill store.

Extracts backend/performance/capability entities from observation text
and stores them as routing skills for future reference.
"""

from __future__ import annotations

import logging
import time

from developer_skills import SkillResult

_log = logging.getLogger(__name__)


def learn(observation: str) -> SkillResult:
    """Store an observation as a routing skill.

    Examples:
        - "scnet_qwen72b is fast for Python refactoring"
        - "groq llama70b struggles with large context (>8k tokens)"
    """
    t0 = time.time()
    details: list[str] = []
    evidence: list[str] = []

    if not observation.strip():
        return SkillResult(
            ok=False, skill="learn",
            summary="Empty observation — nothing to learn",
        )

    skill_key = _extract_skill_key(observation)
    skill_data = {
        "observation": observation,
        "key": skill_key,
        "source": "manual_learn",
    }

    details.append(f"## Observation: {observation}")
    details.append(f"## Skill key: {skill_key}")

    try:
        from context_pipeline.skill_store import get_skill_store
        store = get_skill_store()
        store.crystallize(
            messages=[{"role": "user", "content": observation}],
            scenario="learn",
            backend=skill_key,
            latency_ms=0,
            success=True,
        )
        details.append("## Stored in skill_store (L3)")
        evidence.append("skill_store_ok")
    except Exception as exc:
        details.append(f"## skill_store unavailable: {exc}")
        _log.debug("skill_store not available: %s", exc)

    try:
        from context_pipeline.hierarchical_memory import get_hierarchical_memory
        hmem = get_hierarchical_memory()
        hmem.store_skill(skill_key, skill_data)
        details.append("## Stored in hierarchical_memory (L3)")
        evidence.append("hmem_ok")
    except Exception as exc:
        details.append(f"## hierarchical_memory unavailable: {exc}")

    duration = (time.time() - t0) * 1000
    evidence.append(f"learn_duration:{duration:.0f}ms")

    return SkillResult(
        ok=True,
        skill="learn",
        summary=f"Learned: {skill_key}",
        details=details,
        evidence=evidence,
    )


def _extract_skill_key(text: str) -> str:
    words = text.lower().split()
    keywords = []
    for word in words:
        cleaned = word.strip(".,!?;:'\"")
        if len(cleaned) > 3 and cleaned not in ("the", "and", "for", "with", "that", "this", "from"):
            keywords.append(cleaned)
        if len(keywords) >= 4:
            break
    return "_".join(keywords) if keywords else "unknown_observation"
