#!/usr/bin/env python3
"""Suggest LiMa startup alert thresholds from Prometheus histogram samples."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_QUERY = "lima_startup_phase_duration_ms_bucket"
BUCKETS_MS = [10.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0, 30000.0, 60000.0]


def _parse_bucket(raw: str) -> float:
    return float("inf") if raw == "+Inf" else float(raw)


def parse_prometheus_vector(payload: dict[str, Any]) -> list[tuple[str, float, int]]:
    """Return (phase, le, count) tuples from a Prometheus vector response."""
    samples: list[tuple[str, float, int]] = []
    for item in payload.get("data", {}).get("result", []):
        metric = item.get("metric", {})
        phase = metric.get("phase")
        le = metric.get("le")
        value = item.get("value", [None, "0"])[1]
        if not phase or le is None:
            continue
        samples.append((phase, _parse_bucket(str(le)), int(float(value))))
    return samples


def _next_bucket(value: float) -> float:
    for bucket in BUCKETS_MS:
        if bucket > value:
            return bucket
    return BUCKETS_MS[-1]


def _max_observed_bucket(rows: list[tuple[float, int]]) -> tuple[float, int]:
    total = 0
    observed = 0.0
    for bucket, count in sorted(rows, key=lambda item: item[0]):
        if bucket == float("inf"):
            total = count
        elif count > 0:
            observed = bucket
    return observed, total


def summarize_phase_buckets(samples: list[tuple[str, float, int]]) -> list[dict[str, float | int | str]]:
    """Summarize startup histogram buckets and suggest conservative thresholds."""
    grouped: dict[str, list[tuple[float, int]]] = {}
    for phase, bucket, count in samples:
        grouped.setdefault(phase, []).append((bucket, count))

    result: list[dict[str, float | int | str]] = []
    for phase in sorted(grouped):
        max_observed, total = _max_observed_bucket(grouped[phase])
        warning = _next_bucket(max_observed)
        critical = _next_bucket(warning)
        result.append(
            {
                "phase": phase,
                "samples": total,
                "max_observed_ms": max_observed,
                "warning_ms": warning,
                "critical_ms": critical,
            }
        )
    return result


def _format_ms(value: float | int | str) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render_markdown(summary: list[dict[str, float | int | str]]) -> str:
    """Render a Chinese Markdown report for progress/docs sharing."""
    lines = [
        "# LiMa 启动阈值建议",
        "",
        "| phase | samples | max_observed_ms | warning_ms | critical_ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            "| {phase} | {samples} | {max_observed_ms} | {warning_ms} | {critical_ms} |".format(
                phase=row["phase"],
                samples=row["samples"],
                max_observed_ms=_format_ms(row["max_observed_ms"]),
                warning_ms=_format_ms(row["warning_ms"]),
                critical_ms=_format_ms(row["critical_ms"]),
            )
        )
    if not summary:
        lines.append("| 无样本 | 0 | 0 | 0 | 0 |")
    lines.append("")
    return "\n".join(lines)


def fetch_prometheus_vector(base_url: str, query: str = DEFAULT_QUERY) -> dict[str, Any]:
    """Fetch an instant-vector query from Prometheus."""
    url = base_url.rstrip("/") + "/api/v1/query?" + urllib.parse.urlencode({"query": query})
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def _load_payload(path: str | None, prometheus_url: str | None) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if prometheus_url:
        return fetch_prometheus_vector(prometheus_url)
    raise SystemExit("Provide --input or --prometheus-url")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Prometheus /api/v1/query JSON file")
    parser.add_argument("--prometheus-url", help="Prometheus base URL, e.g. http://117.72.118.95:9090")
    args = parser.parse_args()

    payload = _load_payload(args.input, args.prometheus_url)
    summary = summarize_phase_buckets(parse_prometheus_vector(payload))
    print(render_markdown(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
