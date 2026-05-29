"""SM-2-inspired review scheduling for risky modules and weak points."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import ReviewSchedule, WeakPoint


def schedule_for_weak_point(weak: WeakPoint, now: datetime | None = None) -> ReviewSchedule:
    now = now or datetime.now(timezone.utc)
    interval = 1 if weak.severity.lower() in {"p0", "p1", "high"} else 3
    if weak.recurrence_count >= 3:
        interval = 1
    return ReviewSchedule(
        target_type="weak_point",
        target_id=f"{weak.project}:{weak.kind}:{weak.target}",
        due_at=(now + timedelta(days=interval)).isoformat(),
        reason=f"{weak.kind} recurrence={weak.recurrence_count}: {weak.description[:120]}",
        interval_days=interval,
        ease_factor=2.5,
    )


def update_after_check(schedule: ReviewSchedule, success: bool, now: datetime | None = None) -> ReviewSchedule:
    now = now or datetime.now(timezone.utc)
    if success:
        interval = min(90, max(1, int(round(schedule.interval_days * schedule.ease_factor))))
        ease = min(3.0, schedule.ease_factor + 0.1)
    else:
        interval = 1
        ease = max(1.3, schedule.ease_factor - 0.3)
    return ReviewSchedule(
        target_type=schedule.target_type,
        target_id=schedule.target_id,
        due_at=(now + timedelta(days=interval)).isoformat(),
        reason=schedule.reason,
        interval_days=interval,
        ease_factor=round(ease, 2),
    )
