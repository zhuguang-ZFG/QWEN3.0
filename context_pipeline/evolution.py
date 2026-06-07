"""GEP Evolution Strategies — Evolver-inspired routing mode switching.

Four routing evolution strategies based on system state:
- balanced: Normal operation (50% explore, 30% optimize, 20% repair)
- innovate: Try new backends aggressively (80% explore, 15% optimize, 5% repair)
- harden: Stick to proven paths (20% explore, 40% optimize, 40% repair)
- repair: Emergency mode, only use most reliable backends (0% explore, 20% optimize, 80% repair)

Strategy auto-selection based on:
- Error rate in last N requests
- Fallback trigger frequency
- Backend availability
"""

from dataclasses import dataclass
from enum import Enum


class EvolutionStrategy(Enum):
    BALANCED = "balanced"
    INNOVATE = "innovate"
    HARDEN = "harden"
    REPAIR = "repair"


@dataclass
class StrategyConfig:
    """Configuration for a routing evolution strategy."""

    name: str
    explore_weight: float
    optimize_weight: float
    repair_weight: float
    max_ensemble_size: int
    prefer_proven: bool
    allow_weak_backends: bool


STRATEGY_CONFIGS = {
    EvolutionStrategy.BALANCED: StrategyConfig(
        name="balanced", explore_weight=0.5, optimize_weight=0.3,
        repair_weight=0.2, max_ensemble_size=3,
        prefer_proven=False, allow_weak_backends=True,
    ),
    EvolutionStrategy.INNOVATE: StrategyConfig(
        name="innovate", explore_weight=0.8, optimize_weight=0.15,
        repair_weight=0.05, max_ensemble_size=3,
        prefer_proven=False, allow_weak_backends=True,
    ),
    EvolutionStrategy.HARDEN: StrategyConfig(
        name="harden", explore_weight=0.2, optimize_weight=0.4,
        repair_weight=0.4, max_ensemble_size=2,
        prefer_proven=True, allow_weak_backends=False,
    ),
    EvolutionStrategy.REPAIR: StrategyConfig(
        name="repair", explore_weight=0.0, optimize_weight=0.2,
        repair_weight=0.8, max_ensemble_size=1,
        prefer_proven=True, allow_weak_backends=False,
    ),
}


def auto_select_strategy(
    recent_error_rate: float,
    recent_fallback_rate: float,
    backends_available: int,
    quality_trend: str = "stable",
) -> EvolutionStrategy:
    """Auto-select routing strategy based on system health and quality signals.

    Args:
        recent_error_rate: Error rate in last N requests (0.0-1.0)
        recent_fallback_rate: Fallback trigger rate (0.0-1.0)
        backends_available: Number of healthy backends
        quality_trend: Overall quality trend ("improving", "declining", "stable")
    """
    if recent_error_rate > 0.5 or backends_available < 3:
        return EvolutionStrategy.REPAIR

    # Quality feedback loop: declining quality triggers HARDEN
    if quality_trend == "declining":
        if recent_error_rate > 0.1 or recent_fallback_rate > 0.2:
            return EvolutionStrategy.HARDEN
        # Even without high errors, declining quality warrants caution
        if recent_error_rate > 0.05:
            return EvolutionStrategy.HARDEN

    if recent_error_rate > 0.2 or recent_fallback_rate > 0.3:
        return EvolutionStrategy.HARDEN

    # Quality feedback loop: stable high quality enables INNOVATE
    if recent_error_rate < 0.05 and recent_fallback_rate < 0.1:
        if quality_trend == "improving" or quality_trend == "stable":
            return EvolutionStrategy.INNOVATE
        return EvolutionStrategy.BALANCED

    return EvolutionStrategy.BALANCED


def get_strategy_config(strategy: EvolutionStrategy) -> StrategyConfig:
    """Get configuration for a given strategy."""
    return STRATEGY_CONFIGS[strategy]


def apply_strategy_to_backends(
    backends: list[str],
    strategy: EvolutionStrategy,
    proven_backends: list[str] | None = None,
) -> list[str]:
    """Filter and reorder backends based on current evolution strategy."""
    config = STRATEGY_CONFIGS[strategy]
    proven = set(proven_backends or [])

    if config.prefer_proven and proven:
        proven_list = [b for b in backends if b in proven]
        others = [b for b in backends if b not in proven]
        result = proven_list + others
    else:
        result = list(backends)

    return result[:config.max_ensemble_size * 3]
