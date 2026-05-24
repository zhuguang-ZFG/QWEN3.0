from datetime import datetime, timezone

from mastery_loop import (
    MasteryStore,
    ModuleMastery,
    apply_event_to_module,
    from_pytest_output,
    from_review_finding,
    recommendations_for_files,
    schedule_for_weak_point,
    update_after_check,
    weak_points_from_event,
)
from mastery_loop.models import MasteryEvent, WeakPoint


def test_store_records_event_without_raw_secret(tmp_path):
    store = MasteryStore(tmp_path / "mastery.db")
    secret_summary = "bad " + "tok" + "en=super-secret in routes/admin.py"
    secret_ref = "sk-" + "thisshouldnotpersist12345"
    event = MasteryEvent(
        source="review",
        project="LiMa",
        outcome="fail",
        summary=secret_summary,
        files=["routes/admin.py"],
        modules=["routes"],
        score=-0.8,
        severity="p1",
        evidence_ref=secret_ref,
    )

    saved = store.append_event(event)
    events = store.list_events("LiMa")

    assert saved.summary == "bad [REDACTED] in routes/admin.py"
    assert "[REDACTED]" in events[0].evidence_ref
    assert "super-secret" not in str(events)
    assert ("sk-" + "thisshouldnotpersist") not in str(events)


def test_weak_point_recurrence_and_schedule(tmp_path):
    store = MasteryStore(tmp_path / "mastery.db")
    weak = WeakPoint(
        project="LiMa",
        kind="test_failure",
        target="server.py",
        description="stream footer failed",
        severity="high",
        last_evidence_ref="pytest#1",
    )

    first = store.add_weak_point(weak)
    second = store.add_weak_point(weak)
    schedule = schedule_for_weak_point(second, now=datetime(2026, 5, 24, tzinfo=timezone.utc))
    store.upsert_schedule(schedule)

    assert first.recurrence_count == 1
    assert second.recurrence_count == 2
    assert store.list_weak_points("LiMa")[0].recurrence_count == 2
    assert store.list_schedules()[0].target_id == "LiMa:test_failure:server.py"


def test_pytest_adapter_and_module_scoring(tmp_path):
    event = from_pytest_output(
        "LiMa",
        "FAILED tests/test_stream_footer.py::test_stream_footer - AssertionError",
        evidence_ref="pytest://stream-footer",
    )
    weak_points = weak_points_from_event(event)
    current = ModuleMastery(project="LiMa", module="tests")
    updated = apply_event_to_module(current, event, "tests")

    assert event.outcome == "fail"
    assert event.files == ["tests/test_stream_footer.py"]
    assert weak_points[0].kind == "test_failure"
    assert updated.stability_score < current.stability_score
    assert updated.test_confidence < current.test_confidence


def test_recommendations_for_touched_weak_file(tmp_path):
    store = MasteryStore(tmp_path / "mastery.db")
    weak = store.add_weak_point(
        WeakPoint(
            project="LiMa",
            kind="review_risk",
            target="routes/admin.py",
            description="admin auth needs extra review",
            severity="p1",
            last_evidence_ref="review://admin-auth",
        )
    )
    store.upsert_schedule(schedule_for_weak_point(weak))
    store.upsert_module(
        ModuleMastery(
            project="LiMa",
            module="routes",
            stability_score=0.3,
            review_risk=0.7,
            deploy_risk=0.2,
        )
    )

    recommendations = recommendations_for_files(store, "LiMa", ["routes/admin.py"])
    due = update_after_check(store.list_schedules()[0], success=True)

    assert recommendations
    assert recommendations[0][0].priority == "high"
    assert recommendations[0][1].evidence_refs == ["review://admin-auth"]
    assert due.interval_days > 1


def test_review_finding_adapter_extracts_file_and_severity():
    event = from_review_finding(
        "LiMa",
        "P0",
        "routes/admin.py leaks an auth boundary",
        evidence_ref="review://p0",
    )

    assert event.files == ["routes/admin.py"]
    assert event.severity == "p0"
    assert event.score < -0.8
