# Prometheus Metrics Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LiMa's default-off Prometheus/OpenMetrics endpoint fail visibly when enabled incorrectly and record request/backend gauges without silent downgrade.

**Architecture:** Keep Prometheus support inside `observability/` and expose it only through the existing private ops router. The feature remains disabled unless `LIMA_PROMETHEUS_METRICS=1`; when enabled, missing `prometheus_client` is an explicit startup/runtime error instead of an empty scrape.

**Tech Stack:** FastAPI, `prometheus_client` when configured, existing LiMa ops routes and pytest suite.

---

### Task 1: Tests for Fail-Visible Metrics

**Files:**
- Modify: `tests/test_ops_metrics.py`

- [x] **Step 1: Add tests for default-off and enabled metrics**

Add focused tests that reload `observability.prometheus_metrics` after changing
`LIMA_PROMETHEUS_METRICS`. The tests must assert:

```python
def test_prometheus_metrics_disabled_returns_404(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    monkeypatch.delenv("LIMA_PROMETHEUS_METRICS", raising=False)
    reload_prometheus_metrics()
    response = client.get("/v1/ops/metrics/prometheus", auth_headers)
    assert response.status_code == 404


def test_prometheus_metrics_records_request_when_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_PROMETHEUS_METRICS", "1")
    metrics = reload_prometheus_metrics()
    metrics.record_request("test_backend", "success", 123.0)
    text = metrics.generate_metrics().decode("utf-8")
    assert "lima_requests_total" in text
    assert 'backend="test_backend"' in text
```

- [x] **Step 2: Add dependency-missing test**

Patch Python import to raise `ImportError` for `prometheus_client`, reload the
module with `LIMA_PROMETHEUS_METRICS=1`, and assert `metrics.validate_startup()`
raises `RuntimeError` with `prometheus_client` in the message.

- [x] **Step 3: Add exporter lifecycle test**

Reload `observability.prometheus_exporter`, monkeypatch
`observability.prometheus_metrics.is_enabled` to return `False`, call
`start_exporter()`, and assert no thread starts. Then monkeypatch it to return
`True`, patch the exporter loop to a no-op, call `start_exporter()` and
`stop_exporter()`, and assert the lifecycle is idempotent.

### Task 2: Implement Metrics Module

**Files:**
- Modify: `observability/prometheus_metrics.py`

- [x] **Step 1: Replace silent lazy import with explicit validation**

Add:

```python
def validate_startup() -> None:
    if not is_enabled():
        return
    _load_prometheus_client()
```

`_load_prometheus_client()` must raise `RuntimeError` if the dependency is
missing while metrics are enabled. Disabled metrics should remain a no-op.

- [x] **Step 2: Make instrument creation idempotent**

Track instrument initialization in module state. Avoid duplicate registration
when tests reload or `record_request()` is called multiple times. Use a private
registry or explicit one-time creation so repeated startup does not crash.

- [x] **Step 3: Keep scrape output explicit**

`generate_metrics()` must return bytes only when enabled and initialized. If
enabled but broken, it should raise the same explicit runtime error rather than
returning a fake success payload.

### Task 3: Implement Exporter Lifecycle

**Files:**
- Create: `observability/prometheus_exporter.py`

- [x] **Step 1: Keep exporter default-off**

`start_exporter()` checks `prometheus_metrics.is_enabled()` first. Disabled
state returns without importing `prometheus_client`.

- [x] **Step 2: Validate before thread start**

When enabled, call `prometheus_metrics.validate_startup()` before launching the
daemon thread. Missing dependency must be logged as an error and re-raised.

- [x] **Step 3: Stop cleanly**

`stop_exporter()` sets an event and joins for at most five seconds. It must be
safe to call when no thread exists.

### Task 4: Wire Production Paths

**Files:**
- Modify: `routes/request_tracking.py`
- Modify: `server_lifespan.py`
- Modify: `routes/ops_metrics.py`

- [x] **Step 1: Remove silent import pass**

Replace `except ImportError: pass` in the touched production path with debug or
warning logs that state the skipped optional helper.

- [x] **Step 2: Record request metrics after in-memory stats**

`routes.request_tracking.record_request()` should call
`observability.prometheus_metrics.record_request()` after normal LiMa stats are
updated. Failure must be logged at debug level with exception class and must not
break the user request while metrics are disabled.

- [x] **Step 3: Return 503 for broken enabled metrics**

`/v1/ops/metrics/prometheus` returns:

```text
404 when LIMA_PROMETHEUS_METRICS is disabled
503 when enabled but the dependency/configuration is broken
200 text/plain when enabled and healthy
```

### Task 5: Verification and Closeout

**Files:**
- Modify: `STATUS.md`
- Modify: `docs/LIMA_MEMORY_CN.md`
- Modify: `progress.md`
- Modify: `findings.md`

- [x] **Step 1: Run focused tests**

Run:

```powershell
.\.venv310\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_ops_metrics.py -q
```

Expected: all focused ops metrics tests pass.

- [x] **Step 2: Run hygiene gates**

Run:

```powershell
.\.venv310\Scripts\python.exe scripts\run_pre_commit_check.py
.\.venv310\Scripts\python.exe -m py_compile observability/prometheus_metrics.py observability/prometheus_exporter.py routes/request_tracking.py server_lifespan.py routes/ops_metrics.py
```

Expected: ruff, staged diff checks, and compile checks pass.

- [x] **Step 3: Deploy default-off slice**

Deploy only touched runtime files. VPS smoke must prove public `/health` still
returns 200. During execution, the current VPS was found to already have
`LIMA_PROMETHEUS_METRICS=1`, so authenticated Prometheus smoke correctly
returned `200` on `chat.donglicao.com`; `api.donglicao.com` remained edge `404`.

- [x] **Step 4: Commit and push**

Stage only this slice, commit with `feat: harden prometheus metrics`, push to
GitHub `origin`, and push Gitee only if a Gitee remote exists.
