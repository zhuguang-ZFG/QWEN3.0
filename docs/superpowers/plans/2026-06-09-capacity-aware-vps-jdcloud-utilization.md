# Capacity Aware VPS JDCloud Utilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LiMa deployment capacity-aware on the primary VPS and give the JDCloud node a safe, read-only path toward becoming a real monitoring/probe asset.

**Architecture:** Keep primary LiMa traffic on the Aliyun VPS and `chat.donglicao.com`. Add deploy-time capacity checks and automatic pre-upload backups to the existing unified deploy script. Add a separate JDCloud read-only smoke command that reports capacity, service state, and LiMa scrape reachability without storing secrets or opening new public API surfaces.

**Tech Stack:** Python, Paramiko with strict host-key policy, existing `scripts.deploy_common`, pytest.

---

### Task 1: Primary VPS Capacity and Backup Gate

**Files:**
- Modify: `scripts/deploy_unified.py`
- Modify: `tests/test_deploy_unified.py`

- [x] **Step 1: Add tests for capacity parsing and backup**

Add tests that prove:

```python
capacity = deploy_unified.parse_capacity_output(
    "disk_free_mb=2048\nmem_available_mb=512\n"
)
assert capacity["disk_free_mb"] == 2048
assert capacity["mem_available_mb"] == 512
```

and:

```python
backup = deploy_unified.prepare_remote_deploy(["server.py"], label="unit test")
assert backup["ok"] is True
assert backup["backup_path"].startswith("/opt/lima-router/backups/unit-test-")
```

- [x] **Step 2: Implement capacity preflight**

`prepare_remote_deploy()` must connect with `configure_ssh_host_keys()`, run a
read-only remote check for free disk under `/opt/lima-router` and
`MemAvailable`, and fail before upload if below configurable thresholds:

```text
LIMA_DEPLOY_MIN_FREE_MB default 512
LIMA_DEPLOY_MIN_MEM_MB default 128
```

- [x] **Step 3: Implement automatic backup**

Before any non-dry-run upload, tar the requested remote files into:

```text
/opt/lima-router/backups/<safe-label>-YYYYMMDD_HHMMSS/runtime-before.tgz
```

The backup must happen before SFTP upload and must print the rollback path.

### Task 2: JDCloud Read-Only Smoke Command

**Files:**
- Create: `scripts/check_jdcloud_node.py`
- Create/Modify: `tests/test_jdcloud_node_check.py`
- Modify: `docs/ops/JDCLOUD_RUNTIME_STATUS.md`

- [x] **Step 1: Add tests for sanitized output**

The test should monkeypatch the SSH runner and assert the script emits JSON with
these keys and no secrets:

```python
assert data["host"] == "117.72.118.95"
assert data["role"] == "secondary_probe_monitoring"
assert data["disk_free_mb"] == 2048
assert "password" not in json.dumps(data).lower()
```

- [x] **Step 2: Implement read-only remote check**

The script reads:

```text
JDCLOUD_HOST default 117.72.118.95
JDCLOUD_USER default root
JDCLOUD_SSH_KEY_PATH optional
```

It must use strict host-key policy, run only read-only commands, and report:

```text
disk_free_mb, mem_available_mb, loadavg, lima_probe_timer, lima_probe_service,
prometheus_service, chat_prometheus_http_code
```

- [x] **Step 3: Document the JDCloud role**

Update `docs/ops/JDCLOUD_RUNTIME_STATUS.md` so the node's first production role
is explicit:

```text
1. scrape or probe primary LiMa health/Prometheus;
2. run provider discovery/probe timers;
3. never serve as a second public LiMa API without a separate review.
```

### Task 3: Verification and Closeout

**Files:**
- Modify: `STATUS.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `docs/LIMA_MEMORY.md`

- [x] **Step 1: Run focused tests**

Run:

```powershell
.\.venv310\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_deploy_unified.py tests/test_jdcloud_node_check.py -q
```

- [x] **Step 2: Run gates**

Run:

```powershell
.\.venv310\Scripts\python.exe scripts\run_pre_commit_check.py
.\.venv310\Scripts\python.exe -m py_compile scripts/deploy_unified.py scripts/check_jdcloud_node.py
```

- [x] **Step 3: Runtime smoke**

Use `scripts/deploy_unified.py --dry-run --files scripts/deploy_unified.py` to
prove the file list is safe. If JDCloud SSH credentials are available via key
and known_hosts, run:

```powershell
.\.venv310\Scripts\python.exe scripts\check_jdcloud_node.py --json
```

Record whether the check passed or which credential/host-key prerequisite is
missing. Do not fall back to password files or untracked helper scripts.

- [x] **Step 4: Commit and push**

Commit with `chore: add capacity-aware deploy preflight` and push to GitHub
`origin`. Push Gitee only if a mirror remote exists.
