"""Agent evaluation harness for LiMa Server."""

from .task_score import TaskScore, EvalResult, can_auto_promote
from .regression_suite import RegressionEntry, RegressionSuite

__all__ = [
    "TaskScore",
    "EvalResult",
    "can_auto_promote",
    "RegressionEntry",
    "RegressionSuite",
]
