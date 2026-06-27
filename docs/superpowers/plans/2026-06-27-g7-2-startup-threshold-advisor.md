# G7.2 启动告警阈值校准工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个离线/远程可用的启动阶段 Prometheus 样本分析工具，用真实 `lima_startup_phase_duration_ms_*` 数据给出 G7 告警阈值建议。

**Architecture:** 新增 `scripts/startup_threshold_advisor.py`，职责限定为解析 Prometheus `/api/v1/query` 返回的 instant-vector JSON、按 phase 计算样本、最大值与建议 warning/critical 阈值，并输出 Markdown 报告。测试覆盖纯函数，不需要真实 Prometheus；真实环境可通过脚本 URL 参数查询京东云 Prometheus。

**Tech Stack:** Python 3 标准库（argparse/json/urllib）、pytest、ruff、py_compile、现有 LiMa 文档与 progress 记录。

---

## File Structure

- Create: `scripts/startup_threshold_advisor.py`
  - `parse_prometheus_vector(payload)`：解析 Prometheus query JSON，提取 phase/bucket/count 样本。
  - `summarize_phase_buckets(samples)`：按 phase 计算样本总量、最大观测 bucket、warning/critical 建议。
  - `render_markdown(summary)`：生成中文 Markdown 报告。
  - `main()`：支持 `--input` 本地 JSON 和 `--prometheus-url` 远程查询。
- Create: `tests/test_startup_threshold_advisor.py`
  - 覆盖 Prometheus JSON 解析、阈值建议、空样本、Markdown 输出。
- Modify: `deploy/prometheus/README.md`
  - 增加 G7.2 阈值校准工具用法。
- Modify: `progress.md`
  - 增加 G7.2 结项证据。

---

### Task 1: Write Failing Tests

**Files:**
- Create: `tests/test_startup_threshold_advisor.py`

- [ ] **Step 1: Create the failing test file**

```python
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
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_startup_threshold_advisor.py -q --tb=short
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.startup_threshold_advisor'`.

---

### Task 2: Implement Threshold Advisor

**Files:**
- Create: `scripts/startup_threshold_advisor.py`

- [ ] **Step 1: Write minimal implementation**

```python
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
```

- [ ] **Step 2: Run tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_startup_threshold_advisor.py -q --tb=short
```

Expected: `4 passed`.

---

### Task 3: Document Usage

**Files:**
- Modify: `deploy/prometheus/README.md`
- Modify: `progress.md`

- [ ] **Step 1: Add README section**

Add under Alertmanager section:

```markdown
### 启动阈值校准（G7.2）

积累真实启动样本后，可用 `scripts/startup_threshold_advisor.py` 根据 Prometheus histogram bucket 给出保守阈值建议：

```bash
python scripts/startup_threshold_advisor.py --prometheus-url http://117.72.118.95:9090
```

脚本读取 `lima_startup_phase_duration_ms_bucket`，按 phase 输出样本数、最大观测 bucket、建议 warning/critical 阈值。建议 7 天后结合业务经验再调整 `deploy/prometheus/startup_alerts.yml`。
```

- [ ] **Step 2: Add progress evidence**

Add a concise G7.2 entry near the top of `progress.md` with implemented files and verification commands.

---

### Task 4: Verification and Review

**Files:**
- All changed files

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_startup_threshold_advisor.py tests/test_jdcloud_alertmanager.py tests/test_prometheus_startup_alerts.py -q --tb=short
```

Expected: all pass.

- [ ] **Step 2: Run lint/type/size checks**

Run:

```bash
D:/QWEN3.0/.venv310/Scripts/python.exe -m py_compile scripts/startup_threshold_advisor.py tests/test_startup_threshold_advisor.py
D:/QWEN3.0/.venv310/Scripts/ruff.exe check scripts/startup_threshold_advisor.py tests/test_startup_threshold_advisor.py
D:/QWEN3.0/.venv310/Scripts/pyright.exe scripts/startup_threshold_advisor.py tests/test_startup_threshold_advisor.py
D:/QWEN3.0/.venv310/Scripts/python.exe scripts/check_code_size.py scripts/startup_threshold_advisor.py tests/test_startup_threshold_advisor.py
```

Expected: py_compile OK, ruff OK, pyright 0 errors, size PASS.

- [ ] **Step 3: Run lima-review**

Review changed files for LiMa hard rules, no secrets, no silent downgrade, file/function size, docs language.

- [ ] **Step 4: Commit and push**

```bash
git add scripts/startup_threshold_advisor.py tests/test_startup_threshold_advisor.py deploy/prometheus/README.md progress.md docs/superpowers/plans/2026-06-27-g7-2-startup-threshold-advisor.md .omk/state/ralph-state.json
git commit -m "feat(observability): add startup threshold advisor"
git push origin main
```

---

## Self-Review

- Spec coverage: covers parse, summarize, render, CLI, docs, progress, verification.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: `parse_prometheus_vector`, `summarize_phase_buckets`, and `render_markdown` signatures match tests and implementation steps.
