# Xiaozhi Server Deprecation And Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire `xiaozhi-server` as a runtime dependency for `esp32S_XYZ` after LiMa Direct Device Gateway replaces its device-session, command, and uplink responsibilities.

**Architecture:** Treat `xiaozhi-server` as a migration reference until LiMa owns the direct U8 protocol. Do not delete runtime code until equivalent LiMa Device Gateway behavior, product-side direct U8 mode, and hardware-gated safety evidence exist. The removal is cross-repo: product code changes land in `D:\GIT\esp32S_XYZ`, then the main LiMa repo advances the submodule pointer and records evidence.

**Tech Stack:** LiMa FastAPI/Python, `esp32S_XYZ` U8 firmware C/C++, Python fake-device tests, Java manager-api, existing Edge-A/B/C/D schemas, Git submodules.

---

## Current Decision

`xiaozhi-server` can be removed from the target runtime, but it must not be
physically deleted before its responsibilities are either replaced by LiMa or
explicitly rejected as no longer needed.

Current target:

```text
U8 AI_MCU
  <-> LiMa Device Gateway (/device/v1/ws)
  <-> LiMa backend capabilities
  <-> U1 MOTOR_MCU through existing Edge-D UART JSON
```

`xiaozhi-server` is legacy after this plan begins. It remains useful as a
migration reference for U8 WebSocket handling, `motion_task` delivery,
`motion_event` uplink, `self_check`, `device_info`, voice intent mapping, OTA
planning bridges, voiceprint cache behavior, and existing tests.

## Removal Gates

Do not delete or quarantine `server/xiaozhi-esp32-server/main/xiaozhi-server`
until all gates below are true and recorded:

1. LiMa `/device/v1/ws` accepts U8 `hello`, `heartbeat`, `transcript`,
   `motion_event`, `device_info`, and `self_check` frames.
2. LiMa can send bounded `motion_task` frames to a fake U8.
3. The product repo has a fake LiMa U8 client that passes without real
   hardware.
4. U8 firmware has LiMa direct mode for `hello`, `heartbeat`, `motion_task`,
   and `motion_event`.
5. U8 keeps Edge-D UART JSON to U1 unchanged.
6. Deterministic commands pass: `写你好`, `画一个星星`, `归零`, `暂停`, `继续`,
   `停止`, and `设备信息`.
7. Real-device smoke confirms `stop` or `estop`, `home`, `get_device_info`, a
   very small path, progress uplink, and final `done` or safe failure.
8. Production docs no longer instruct users to run `xiaozhi-server`.
9. CI and local verification no longer depend on `xiaozhi-server` runtime
   startup.
10. Main LiMa docs record the product commit that proved direct mode.

## Files And Ownership

Main LiMa repo files:

- Create or modify: `routes/device_gateway.py`
- Create or modify: `device_gateway/protocol.py`
- Create or modify: `device_gateway/auth.py`
- Create or modify: `device_gateway/sessions.py`
- Create or modify: `device_gateway/tasks.py`
- Create or modify: `device_gateway/intent.py`
- Create or modify: `device_gateway/safety.py`
- Create or modify: `tests/test_device_gateway*.py`
- Modify: `server.py`
- Modify: `docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md`
- Modify: `docs/ONLINE_DISTRIBUTIONS.md` if a public device endpoint is
  exposed
- Modify: `STATUS.md`, `docs/LIMA_MEMORY.md`, and `progress.md`

Product repo files:

- Modify: `D:\GIT\esp32S_XYZ\firmware\u8-xiaozhi\main\application.cc`
- Modify or create: U8 direct LiMa config files under
  `D:\GIT\esp32S_XYZ\firmware\u8-xiaozhi`
- Create: `D:\GIT\esp32S_XYZ\tools\fake_lima_u8\app.py`
- Create: `D:\GIT\esp32S_XYZ\tools\fake_lima_u8\tests\test_app.py`
- Modify: `D:\GIT\esp32S_XYZ\tests\ci\test_edge_d_firmware_static.py`
- Modify: `D:\GIT\esp32S_XYZ\README.md`
- Modify: `D:\GIT\esp32S_XYZ\task_plan.md`
- Modify or remove references in
  `D:\GIT\esp32S_XYZ\server\xiaozhi-esp32-server\docs`

Legacy candidate:

- Quarantine or remove after gates:
  `D:\GIT\esp32S_XYZ\server\xiaozhi-esp32-server\main\xiaozhi-server`

## Task 1: Mark Xiaozhi Server As Legacy Reference

**Files:**

- Modify:
  `D:\GIT\esp32S_XYZ\server\xiaozhi-esp32-server\main\xiaozhi-server\README.md`
- Modify: `D:\GIT\esp32S_XYZ\task_plan.md`
- Modify: `D:\GIT\esp32S_XYZ\README.md`

- [ ] **Step 1: Add a legacy runtime notice**

Add this exact notice near the top of the product repo Xiaozhi server README:

```markdown
> LiMa migration notice: this server is retained as a legacy migration
> reference while `esp32S_XYZ` moves to LiMa Direct Device Gateway. New runtime
> work should target LiMa `/device/v1/ws`; do not add new product features here
> unless the direct-device plan explicitly requires migration evidence.
```

- [ ] **Step 2: Record the decision in the product task plan**

Append this exact section to `D:\GIT\esp32S_XYZ\task_plan.md`:

```markdown
## LiMa Direct Device Gateway Migration

- `xiaozhi-server` is now a legacy migration reference, not the target runtime.
- The target runtime is U8 direct connection to LiMa `/device/v1/ws`.
- Do not physically remove `xiaozhi-server` until LiMa direct mode, fake U8,
  U8 firmware direct mode, and real-device safety smoke are verified.
```

- [ ] **Step 3: Run product doc scan**

Run:

```powershell
cd D:\GIT\esp32S_XYZ
rg -n "legacy migration reference|/device/v1/ws|xiaozhi-server" README.md task_plan.md server\xiaozhi-esp32-server\main\xiaozhi-server\README.md
```

Expected:

- The new legacy notice appears.
- `/device/v1/ws` appears in the task plan.

- [ ] **Step 4: Commit product repo**

```powershell
cd D:\GIT\esp32S_XYZ
git add README.md task_plan.md server\xiaozhi-esp32-server\main\xiaozhi-server\README.md
git commit -m "docs: mark xiaozhi server as legacy"
git push origin main
```

## Task 2: Build LiMa Gateway Parity Inventory

**Files:**

- Create:
  `D:\GIT\esp32S_XYZ\docs\xiaozhi-server-migration-inventory.md`
- Modify:
  `D:\GIT\docs\superpowers\plans\2026-05-24-lima-direct-device-gateway.md`

- [ ] **Step 1: Create the migration inventory**

Create the product repo inventory with this structure:

```markdown
# Xiaozhi Server Migration Inventory

## Runtime Responsibilities

| Responsibility | Existing Xiaozhi source | LiMa replacement | Removal gate |
|---|---|---|---|
| Device WebSocket session | `main/xiaozhi-server/core/websocket_server.py` | LiMa `/device/v1/ws` sessions | Fake U8 hello/heartbeat passes |
| Motion task downlink | `core/api/motion_task_handler.py` and `core/handle/motionHandle.py` | LiMa `device_gateway.tasks` | Fake U8 receives bounded `motion_task` |
| Motion event uplink | `core/handle/textHandler/motionEventMessageHandler.py` | LiMa `motion_event` frame handling | Progress/done persisted or recorded |
| Device info uplink | `core/handle/textHandler/deviceInfoMessageHandler.py` | LiMa `device_info` frame handling | `get_device_info` direct smoke passes |
| Self-check uplink | `core/handle/textHandler/selfCheckMessageHandler.py` | LiMa `self_check` frame handling | Startup self-check direct smoke passes |
| Voice intent mapping | `core/handle/deviceIntentMap.py` | LiMa `device_gateway.intent` | Deterministic command tests pass |
| Voice task submit | `core/handle/intentHandler.py` | LiMa local task creation | `写你好` and `画一个星星` pass |
| Voiceprint cache | `core/utils/voiceprint_cache.py` and `core/api/voiceprint_cache_handler.py` | Later LiMa policy module | Explicitly migrated or rejected |
| OTA plan bridge | `core/api/ota_handler.py` | Later LiMa OTA endpoint | Explicitly migrated or rejected |
```

## Delete Candidates

- `main/xiaozhi-server`

## Preserve Candidates

- Edge-C protocol examples until LiMa direct protocol examples replace them.
- Tests that encode useful command behavior, ported to LiMa direct tests.
```

- [ ] **Step 2: Cross-link main plan**

In `D:\GIT\docs\superpowers\plans\2026-05-24-lima-direct-device-gateway.md`,
add a note under `Phase 0 - Baseline and Design Lock`:

```markdown
- Create `docs/xiaozhi-server-migration-inventory.md` in the product repo and
  map every Xiaozhi runtime responsibility to a LiMa replacement or explicit
  rejection.
```

- [ ] **Step 3: Verify inventory has the required responsibility map**

Run:

```powershell
cd D:\GIT\esp32S_XYZ
rg -n "Runtime Responsibilities|LiMa replacement|Removal gate|Motion task downlink|Voice intent mapping|OTA plan bridge" docs\xiaozhi-server-migration-inventory.md
```

Expected:

- The command prints the table header and the listed responsibilities.

- [ ] **Step 4: Commit both repos**

Product repo:

```powershell
cd D:\GIT\esp32S_XYZ
git add docs\xiaozhi-server-migration-inventory.md
git commit -m "docs: inventory xiaozhi migration"
git push origin main
```

Main repo:

```powershell
cd D:\GIT
git add docs\superpowers\plans\2026-05-24-lima-direct-device-gateway.md esp32S_XYZ
git commit -m "docs: link xiaozhi migration inventory"
git push origin codex/free-web-ai-probe
```

## Task 3: Port Deterministic Intent Rules To LiMa

**Files:**

- Create: `D:\GIT\device_gateway\intent.py`
- Create: `D:\GIT\tests\test_device_gateway_intent.py`

- [ ] **Step 1: Write failing tests**

Create `D:\GIT\tests\test_device_gateway_intent.py`:

```python
from device_gateway.intent import resolve_direct_device_command, resolve_voice_task


def test_resolves_write_text_voice_task():
    task = resolve_voice_task("小智，写你好")

    assert task == {
        "capability": "write_text",
        "source": "voice",
        "params": {"text": "你好", "font_id": "kai_basic_v1"},
    }


def test_resolves_draw_generated_voice_task():
    task = resolve_voice_task("画一个星星")

    assert task == {
        "capability": "draw_generated",
        "source": "voice",
        "params": {"prompt": "星星"},
    }


def test_resolves_direct_stop_command():
    command = resolve_direct_device_command("停止")

    assert command == {"capability": "stop", "params": {}}
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
cd D:\GIT
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_intent.py -q --ignore=active_model
```

Expected:

- Fails because `device_gateway.intent` does not exist.

- [ ] **Step 3: Implement deterministic intent module**

Create `D:\GIT\device_gateway\intent.py`:

```python
from __future__ import annotations

import re
from typing import Any


DEFAULT_WRITE_TEXT_FONT_ID = "kai_basic_v1"


def _normalize_text(text: str) -> str:
    normalized = "".join(str(text or "").strip().lower().split())
    return re.sub(r"[\s,.;:!?，。！？、：；\"'“”‘’]", "", normalized)


def _strip_voice_prefix(text: str) -> str:
    normalized = _normalize_text(text)
    for prefix in ("小智", "你好小智", "xiaozhi", "heyxiaozhi", "lima", "你好lima"):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return normalized


def resolve_direct_device_command(text: str) -> dict[str, Any] | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    rules = (
        ("home", ("归零", "回原点", "回零", "home")),
        ("pause", ("暂停", "pause")),
        ("resume", ("继续", "恢复", "resume")),
        ("stop", ("停止", "停下", "stop")),
        ("get_device_info", ("型号", "设备信息", "机器信息", "硬件版本", "固件版本", "deviceinfo")),
    )
    for capability, tokens in rules:
        if any(_normalize_text(token) in normalized for token in tokens):
            return {"capability": capability, "params": {}}
    return None


def resolve_voice_task(text: str) -> dict[str, Any] | None:
    normalized = _strip_voice_prefix(text)
    if not normalized:
        return None

    write_match = re.match(r"^(?:请)?(?:帮我)?(?:写一下|写出|写)(.+)$", normalized)
    if write_match:
        content = write_match.group(1).strip()
        if content:
            return {
                "capability": "write_text",
                "source": "voice",
                "params": {"text": content, "font_id": DEFAULT_WRITE_TEXT_FONT_ID},
            }

    draw_match = re.match(r"^(?:请)?(?:帮我)?(?:画一个|画一只|画一下|画)(.+)$", normalized)
    if draw_match:
        prompt = draw_match.group(1).strip()
        if prompt:
            return {
                "capability": "draw_generated",
                "source": "voice",
                "params": {"prompt": prompt},
            }

    return None
```

- [ ] **Step 4: Run tests and confirm pass**

Run:

```powershell
cd D:\GIT
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_intent.py -q --ignore=active_model
```

Expected:

- `3 passed`

- [ ] **Step 5: Commit main repo**

```powershell
cd D:\GIT
git add device_gateway\intent.py tests\test_device_gateway_intent.py
git commit -m "feat: add device gateway intent mapping"
git push origin codex/free-web-ai-probe
```

## Task 4: Quarantine Runtime Docs After Gateway Parity

**Files:**

- Modify:
  `D:\GIT\esp32S_XYZ\server\xiaozhi-esp32-server\docs\Deployment.md`
- Modify:
  `D:\GIT\esp32S_XYZ\server\xiaozhi-esp32-server\docs\Deployment_all.md`
- Modify: `D:\GIT\esp32S_XYZ\README.md`

- [ ] **Step 1: Add deprecation text to deployment docs**

Add this text near the top of each Xiaozhi deployment document:

```markdown
> LiMa direct-device migration: this deployment path is legacy for
> `esp32S_XYZ`. New product deployments should use LiMa Device Gateway after
> `/device/v1/ws` and U8 direct mode are verified. Keep this document only for
> migration comparison until the removal gates pass.
```

- [ ] **Step 2: Verify deployment docs mention LiMa direct-device migration**

Run:

```powershell
cd D:\GIT\esp32S_XYZ
rg -n "LiMa direct-device migration|legacy for" server\xiaozhi-esp32-server\docs\Deployment.md server\xiaozhi-esp32-server\docs\Deployment_all.md README.md
```

Expected:

- Both deployment docs match.

- [ ] **Step 3: Commit product repo**

```powershell
cd D:\GIT\esp32S_XYZ
git add README.md server\xiaozhi-esp32-server\docs\Deployment.md server\xiaozhi-esp32-server\docs\Deployment_all.md
git commit -m "docs: deprecate xiaozhi deployment path"
git push origin main
```

## Task 5: Remove Or Quarantine Xiaozhi Runtime

**Files:**

- Move or delete after gates:
  `D:\GIT\esp32S_XYZ\server\xiaozhi-esp32-server\main\xiaozhi-server`
- Modify:
  `D:\GIT\esp32S_XYZ\server\xiaozhi-esp32-server\main\README.md`
- Modify:
  `D:\GIT\esp32S_XYZ\.github\workflows\ci.yml`
- Modify: `D:\GIT\esp32S_XYZ\task_plan.md`

- [ ] **Step 1: Confirm removal gates**

Run the evidence review:

```powershell
cd D:\GIT\esp32S_XYZ
rg -n "LiMa Direct Device Gateway|real-device|/device/v1/ws|xiaozhi-server" docs task_plan.md README.md
```

Expected:

- Evidence exists for LiMa direct mode.
- Evidence exists for real-device safety smoke.
- Product docs no longer require `xiaozhi-server` for target runtime.

- [ ] **Step 2: Prefer quarantine if any migration uncertainty remains**

If any useful reference remains, move instead of delete:

```powershell
cd D:\GIT\esp32S_XYZ
New-Item -ItemType Directory -Force legacy | Out-Null
git mv server\xiaozhi-esp32-server\main\xiaozhi-server legacy\xiaozhi-server
```

If all useful behavior is ported and docs/tests no longer reference runtime
imports, delete:

```powershell
cd D:\GIT\esp32S_XYZ
git rm -r server\xiaozhi-esp32-server\main\xiaozhi-server
```

- [ ] **Step 3: Update CI after quarantine or deletion**

Open `.github\workflows\ci.yml` and remove only jobs or commands that import
or start `main/xiaozhi-server`. Keep schema, GPIO, fake U1, fake Device
Gateway, manager-api, and manager-mobile checks.

- [ ] **Step 4: Run product verification**

Run:

```powershell
cd D:\GIT\esp32S_XYZ
python tools/validate_schemas.py
python tools/check_gpio.py
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest tools.fake_u1.tests.test_app -v
python -m unittest tools.fake_device_server.tests.test_app -v
python -m unittest tools.fake_ai.tests.test_app -v
```

Expected:

- Product tests pass without importing or starting `xiaozhi-server`.

- [ ] **Step 5: Commit product repo**

```powershell
cd D:\GIT\esp32S_XYZ
git add .github\workflows\ci.yml README.md task_plan.md
git add legacy\xiaozhi-server server\xiaozhi-esp32-server\main || exit 0
git commit -m "chore: retire xiaozhi runtime"
git push origin main
```

## Task 6: Advance Main Repo Submodule Pointer

**Files:**

- Modify: `D:\GIT\esp32S_XYZ` submodule pointer
- Modify: `D:\GIT\STATUS.md`
- Modify: `D:\GIT\docs\LIMA_MEMORY.md`
- Modify: `D:\GIT\progress.md`
- Modify: `D:\GIT\docs\ESP32S_XYZ_MANAGEMENT.md`

- [ ] **Step 1: Update main repo submodule pointer**

Run:

```powershell
cd D:\GIT
git -C esp32S_XYZ fetch origin
git -C esp32S_XYZ checkout main
git -C esp32S_XYZ pull --ff-only origin main
git add esp32S_XYZ
```

- [ ] **Step 2: Record removal evidence**

Add a section to `docs\LIMA_MEMORY.md`:

```markdown
## YYYY-MM-DD Xiaozhi Runtime Retirement

- `esp32S_XYZ` no longer requires `xiaozhi-server` for the target runtime.
- Product commit: `<commit hash>`.
- LiMa Device Gateway evidence: `<test command and result>`.
- Product evidence: `<test command and result>`.
- Real-device evidence: `<hardware smoke reference>`.
```

Use the actual date, product commit hash, commands, and evidence references.

- [ ] **Step 3: Run main repo status checks**

Run:

```powershell
cd D:\GIT
git submodule status esp32S_XYZ
git diff --check -- STATUS.md docs\LIMA_MEMORY.md progress.md docs\ESP32S_XYZ_MANAGEMENT.md
```

Expected:

- Submodule points at the pushed product commit.
- Diff check passes.

- [ ] **Step 4: Commit main repo**

```powershell
cd D:\GIT
git add esp32S_XYZ STATUS.md docs\LIMA_MEMORY.md progress.md docs\ESP32S_XYZ_MANAGEMENT.md
git commit -m "chore: advance esp32 direct device runtime"
git push origin codex/free-web-ai-probe
```

## Verification Summary

Before declaring the removal complete, report:

- Product commit hash.
- Main repo commit hash.
- Whether `xiaozhi-server` was quarantined or deleted.
- Main LiMa Device Gateway tests and result.
- Product fake-device tests and result.
- Real U8/U1 safety smoke evidence.
- Secret scan result for changed files.

## Stop Conditions

Stop and do not delete runtime code if:

- Direct LiMa U8 session cannot reconnect cleanly.
- `stop` or `estop` priority is unproven.
- `run_path` workspace bounds are not enforced.
- Any product test still imports `xiaozhi-server` as runtime dependency.
- Real-device smoke is unavailable but the change would affect production
  motion, OTA, provisioning, or voice behavior.
