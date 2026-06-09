# JDCloud Browser Probe Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the JDCloud browser helper a verified production probe asset instead of a service that reports healthy while `/render` fails.

**Architecture:** Keep the browser helper loopback-only on JDCloud port `8092`. Add a cheap readiness endpoint and include a loopback browser render smoke in the JDCloud node check, then install the missing Playwright Chromium runtime on JDCloud and verify `lima-probe.service` records browser probe results.

**Tech Stack:** FastAPI, Playwright, systemd, Paramiko with strict host-key policy, pytest.

---

### Task 1: Browser Helper Readiness Contract

**Files:**
- Modify: `provider_probe/browser_service.py`
- Create: `tests/test_browser_service.py`

- [ ] **Step 1: Add tests for readiness and sanitized launch failure**

Add tests that monkeypatch `_get_browser()` so the readiness endpoint returns
`ready=false` with an error class instead of a stack trace:

```python
def test_ready_reports_browser_launch_failure(monkeypatch):
    async def fail_browser():
        raise RuntimeError("Executable doesn't exist at /root/.cache/ms-playwright/chromium")

    monkeypatch.setattr(browser_service, "_get_browser", fail_browser)
    response = TestClient(browser_service.app).get("/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["ready"] is False
    assert data["error_class"] == "RuntimeError"
    assert "/root/.cache" not in data["error"]
```

Add a second test for render failure conversion:

```python
def test_render_launch_failure_returns_json_error(monkeypatch):
    async def fail_browser():
        raise RuntimeError("Executable doesn't exist at /root/.cache/ms-playwright/chromium")

    monkeypatch.setattr(browser_service, "_get_browser", fail_browser)
    response = TestClient(browser_service.app).post(
        "/render",
        json={"url": "https://example.com", "wait_ms": 1},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["error_class"] == "RuntimeError"
```

- [ ] **Step 2: Implement sanitized readiness**

Add a `_sanitize_error()` helper and `/ready` endpoint. `/health` remains cheap
process liveness, while `/ready` proves the browser can launch:

```python
@app.get("/ready")
async def ready():
    try:
        await _get_browser()
        return {"ready": True, "service": "probe-browser"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "service": "probe-browser",
                "error_class": type(exc).__name__,
                "error": _sanitize_error(str(exc)),
            },
        )
```

Also make `/render` return the same sanitized JSON detail when browser launch
fails before a context exists.

### Task 2: JDCloud Node Check Covers Browser Render

**Files:**
- Modify: `scripts/check_jdcloud_node.py`
- Modify: `tests/test_jdcloud_node_check.py`
- Modify: `docs/ops/JDCLOUD_RUNTIME_STATUS.md`

- [ ] **Step 1: Add tests for browser readiness fields**

Extend the parser test to include:

```python
"browser_health_http_code=200",
"browser_ready_http_code=503",
"browser_render_http_code=500",
```

Assert the parsed JSON includes those fields and remains secret-free.

- [ ] **Step 2: Add loopback browser smoke to remote check**

Extend `REMOTE_CHECK` with read-only loopback curls:

```sh
browser_health=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8092/health 2>/dev/null || echo curl_failed)
browser_ready=$(curl -sS -m 15 -o /dev/null -w '%{http_code}' http://127.0.0.1:8092/ready 2>/dev/null || echo curl_failed)
browser_render=$(curl -sS -m 30 -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8092/render -H 'Content-Type: application/json' -d '{"url":"https://example.com","wait_ms":500}' 2>/dev/null || echo curl_failed)
```

Report `browser_health_http_code`, `browser_ready_http_code`, and
`browser_render_http_code`. Keep `ok` tied to primary LiMa health; browser
readiness is a capability field, not a second public API.

### Task 3: JDCloud Runtime Repair and Closeout

**Files:**
- Modify: `STATUS.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `docs/LIMA_MEMORY.md`

- [ ] **Step 1: Local gates**

Run:

```powershell
.\.venv310\Scripts\python.exe -m py_compile provider_probe/browser_service.py scripts/check_jdcloud_node.py tests/test_browser_service.py tests/test_jdcloud_node_check.py
.\.venv310\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_browser_service.py tests/test_jdcloud_node_check.py -q
.\.venv310\Scripts\python.exe scripts/run_ruff_check.py
```

- [ ] **Step 2: Deploy and repair JDCloud**

Using strict host-key Paramiko and the operator-provided password from
`VPS.txt`, backup `/opt/lima-probe/browser_service.py` and deploy only:

```text
provider_probe/browser_service.py -> /opt/lima-probe/browser_service.py
provider_probe/browser_service.py -> /opt/lima-probe/provider_probe/browser_service.py
scripts/check_jdcloud_node.py -> /opt/lima-router/scripts/check_jdcloud_node.py
```

Then run:

```sh
python3 -m playwright install chromium
systemctl restart lima-probe-browser.service
curl -sS -m 15 http://127.0.0.1:8092/ready
curl -sS -m 45 -X POST http://127.0.0.1:8092/render -H 'Content-Type: application/json' -d '{"url":"https://example.com","wait_ms":500}'
systemctl start lima-probe.service
```

- [ ] **Step 3: Runtime evidence and commit**

Record whether JDCloud `/ready` and `/render` returned `200`, whether
`lima-probe.service` reports browser probe source count above zero, and the
remote backup path. Commit and push to GitHub `origin`.
