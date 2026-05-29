"""LiMa mastery loop: offline module-quality analysis and review scheduling.

CRITICAL: This is an offline/background analysis system. Its outputs
(recommendations, weak points, scores) must NOT be used in the hot-path
routing decisions (server.py, routing_engine.py). Promotion evidence
gates in agent_evolution consume mastery data, but the agent evolution
path is also offline (not in the request-response hot path).

Hot-path routing decisions must only use health_tracker, route_scorer,
and budget_manager, never mastery_loop scores.
"""
from .event_adapter import (
    from_deploy_smoke,
    from_pytest_output,
    from_review_finding,
    from_routing_failure,
    from_tool_audit,
)
from .models import MasteryEvent, ModuleMastery, Recommendation, ReviewSchedule, WeakPoint
from .profile_store import MasteryStore
from .recommender import due_review_recommendations, recommendations_for_files
from .scheduler import schedule_for_weak_point, update_after_check
from .scorer import apply_event_to_module, score_event
from .weak_point_extractor import weak_points_from_event

__all__ = [
    "MasteryEvent",
    "MasteryStore",
    "ModuleMastery",
    "Recommendation",
    "ReviewSchedule",
    "WeakPoint",
    "apply_event_to_module",
    "due_review_recommendations",
    "from_deploy_smoke",
    "from_pytest_output",
    "from_review_finding",
    "from_routing_failure",
    "from_tool_audit",
    "recommendations_for_files",
    "schedule_for_weak_point",
    "score_event",
    "update_after_check",
    "weak_points_from_event",
]
