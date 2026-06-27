"""Tests for scripts/startup_threshold_advisor.py."""

from __future__ import annotations

from scripts.startup_threshold_advisor import (
    parse_prometheus_vector,
    render_markdown,
    summarize_phase_buckets,
)


PROM_PAYLOAD = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {"phase": "health_state.load", "le": "1000.0"},
                "value": [1710000000, "1"],
            },
            {
                "metric": {"phase": "health_state.load", "le": "5000.0"},
                "value": [1710000000, "2"],
            },
            {
                "metric": {"phase": "health_state.load", "le": "+Inf"},
                "value": [1710000000, "2"],
            },
            {
                "metric": {"phase": "context_pipeline.auto_indexer.start", "le": "10000.0"},
                "value": [1710000000, "1"],
            },
            {
                "metric": {"phase": "context_pipeline.auto_indexer.start", "le": "+Inf"},
                "value": [1710000000, "1"],
            },
        ],
    },
}


def test_parse_prometheus_vector_extracts_phase_bucket_counts():
    samples = parse_prometheus_vector(PROM_PAYLOAD)
    assert samples == [
        ("health_state.load", 1000.0, 1),
        ("health_state.load", 5000.0, 2),
        ("health_state.load", float("inf"), 2),
        ("context_pipeline.auto_indexer.start", 10000.0, 1),
        ("context_pipeline.auto_indexer.start", float("inf"), 1),
    ]


def test_summarize_phase_buckets_recommends_thresholds_above_max_bucket():
    samples = parse_prometheus_vector(PROM_PAYLOAD)
    summary = summarize_phase_buckets(samples)
    by_phase = {item["phase"]: item for item in summary}
    assert by_phase["health_state.load"] == {
        "phase": "health_state.load",
        "samples": 2,
        "max_observed_ms": 5000.0,
        "warning_ms": 10000.0,
        "critical_ms": 30000.0,
    }
    assert by_phase["context_pipeline.auto_indexer.start"] == {
        "phase": "context_pipeline.auto_indexer.start",
        "samples": 1,
        "max_observed_ms": 10000.0,
        "warning_ms": 30000.0,
        "critical_ms": 60000.0,
    }


def test_summarize_phase_buckets_handles_empty_input():
    assert summarize_phase_buckets([]) == []


def test_render_markdown_outputs_chinese_report_table():
    summary = summarize_phase_buckets(parse_prometheus_vector(PROM_PAYLOAD))
    report = render_markdown(summary)
    assert "# LiMa 启动阈值建议" in report
    assert "| phase | samples | max_observed_ms | warning_ms | critical_ms |" in report
    assert "health_state.load" in report
    assert "context_pipeline.auto_indexer.start" in report
