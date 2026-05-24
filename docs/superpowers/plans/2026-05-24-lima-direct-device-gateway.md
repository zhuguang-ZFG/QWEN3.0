# LiMa Direct Device Gateway Plan

**Date:** 2026-05-24
**Status:** public route deployed; Redis HA task routing deployed; real hardware still gated
**Scope:** replace the Xiaozhi server runtime dependency for `esp32S_XYZ` with
a LiMa-native U8 device protocol and gateway.

## Goal

Let the `esp32S_XYZ` U8 firmware connect directly to LiMa and use LiMa as the
device backend for listening, command understanding, writing, drawing, status,
and safety-controlled motion. Xiaozhi server code may remain as migration
reference, but the target runtime must not require `xiaozhi-server`.

The clean target path is:

```text
U8 AI_MCU
  <-> LiMa Device Gateway (/device/v1/ws)
  <-> LiMa backend capabilities
      - ASR / command understanding / TTS
      - write_text and draw_generated task creation
      - image/vector generation and run_path projection
      - safety validation and task state
      - device status, self-check, telemetry, OTA planning
  <-> U1 MOTOR_MCU through existing Edge-D UART JSON
```

## Core Decision

Create a new LiMa device routing layer, not a new model routing layer.

Device routing owns:

- device authentication;
- WebSocket sessions;
- heartbeats and reconnects;
- message validation;
- device task state;
- `motion_task` downlink;
- `motion_event`, `device_info`, and `self_check` uplink;
- direct-device safety gates.

Model routing remains in the current LiMa backend registry, `routing_engine`,
`smart_router`, and provider/key-pool stack. Device Gateway calls those
capabilities when it needs ASR, command understanding, image/vector generation,
or TTS.

## Initial Routes

| Route | Protocol | Purpose | First phase |
|---|---|---|---|
| `/device/v1/ws` | WebSocket | U8 long-lived device session | Required |
| `/device/v1/events` | HTTP JSON | Optional fallback for event uplink and fake-device tests | Optional |
| `/device/v1/tasks` | HTTP JSON | Admin/debug task injection for test rigs | Optional and private |
| `/device/v1/health` | HTTP JSON | Gateway readiness and protocol version | Required |

First implementation should live inside the existing LiMa FastAPI service. It
can be split into a separate service only after session volume or isolation
needs justify it.

## Future Hardware Reference Track

The first implementation target stays the writing machine path. External
references for voice, display, and companion hardware are tracked separately in
`docs/reference/HARDWARE_COMPANION_REFERENCES.md` so they inform later hardware
families without expanding the initial safety-critical scope.

Admitted follow-on classes:

- voice AI / ESP32 companion devices, using ElatoAI as a design reference for
  secure WebSocket-style device sessions and realtime audio posture;
- display / transparent companion screens, using the ESP32 TFT transparent-TV
  build as a design reference for visual status, prompt, avatar, or ambient
  companion output;
- multi-capability companion devices that combine motion, voice, and display
  only after each capability has its own schema, adapter, tests, and safety
  gates.

## Proposed Main-Repo Modules

```text
routes/device_gateway.py
device_gateway/protocol.py
device_gateway/auth.py
device_gateway/sessions.py
device_gateway/tasks.py
device_gateway/intent.py
device_gateway/safety.py
device_gateway/transports.py
```

Responsibilities:

- `routes/device_gateway.py`: FastAPI route registration and request handling.
- `protocol.py`: message schemas, protocol version, error envelopes.
- `auth.py`: device token validation without leaking provider secrets.
- `sessions.py`: active `device_id` to WebSocket session map.
- `tasks.py`: task creation, dedupe, state transitions, downlink envelopes.
- `intent.py`: deterministic and model-assisted command mapping.
- `safety.py`: device command allowlist, workspace and motion constraints.
- `transports.py`: abstraction over WebSocket send/receive for unit tests.

## Protocol v1 Messages

Use JSON text frames for control and binary frames only when audio streaming is
introduced. Keep the first milestone text-only so fake U8/fake U1 can prove the
motion path before audio complexity enters.

### U8 to LiMa

```json
{ "type": "hello", "protocol": "lima-device-v1", "device_id": "dev_SN001", "fw_rev": "u8-0.1.0", "capabilities": ["run_path", "audio", "self_check"] }
```

```json
{ "type": "heartbeat", "device_id": "dev_SN001", "uptime_ms": 123456 }
```

```json
{ "type": "transcript", "device_id": "dev_SN001", "text": "画一个星星", "request_id": "u8-req-001" }
```

```json
{ "type": "motion_event", "device_id": "dev_SN001", "task_id": "task-001", "phase": "progress", "progress": { "done_segments": 3, "total_segments": 12, "percent": 25 } }
```

```json
{ "type": "device_info", "device_id": "dev_SN001", "model": "esp32S_XYZ", "hw_rev": "P1", "fw_rev": "u1-0.1.0", "workspace_mm": { "x": 100, "y": 100, "z": 20 } }
```

```json
{ "type": "self_check", "device_id": "dev_SN001", "status": "passed", "checks": [] }
```

### LiMa to U8

```json
{ "type": "hello_ack", "protocol": "lima-device-v1", "server_time": "2026-05-24T00:00:00Z" }
```

```json
{ "type": "motion_task", "task_id": "task-001", "capability": "run_path", "source": "voice", "params": { "feed": 900, "path": [] } }
```

```json
{ "type": "speech", "state": "text", "text": "任务已提交。" }
```

```json
{ "type": "error", "code": "E_INVALID_MESSAGE", "message": "message type is not supported", "request_id": "u8-req-001" }
```

Audio frame support is a later milestone:

- JSON frame starts an audio stream with codec/sample metadata.
- Binary frames carry Opus or PCM chunks.
- JSON frame ends the stream and binds the transcript to a `request_id`.

## Command Mapping

First deterministic commands:

| User command | LiMa task | Notes |
|---|---|---|
| `写你好` | `write_text` -> `run_path` | Reuse existing product projection semantics. |
| `画一个星星` | `draw_generated` -> `run_path` | Start with starter assets or safe SVG generation. |
| `归零` | `home` | Safety-allowed direct command. |
| `暂停` | `pause` | Control command only. |
| `继续` | `resume` | Control command only. |
| `停止` | `stop` | Control command only. |
| `设备信息` | `get_device_info` | Query U1/U8 identity and workspace. |

Free-form LLM interpretation can be added only after deterministic command
coverage and safety rejection tests pass.

## Cross-Repo Work Plan

### Phase 0 - Baseline and Design Lock

- Reproduce current `esp32S_XYZ` fake-device and schema checks.
- Record current U8/Xiaozhi message dependency points.
- Add this plan as the source of truth.

Exit criteria:

- Plan committed in main LiMa repo.
- `esp32S_XYZ` remains unchanged and clean.

### Phase 1 - LiMa Gateway Skeleton

Main repo:

- Add `/device/v1/health`.
- Add `/device/v1/ws` with `hello`, `heartbeat`, and error handling.
- Add in-memory session registry keyed by `device_id`.
- Add protocol unit tests.

No model calls, no motion yet.

Exit criteria:

- Unit tests cover valid hello, duplicate session handling, heartbeat, and bad
  message errors.
- Local route import and FastAPI registration pass.

### Phase 2 - Fake U8 Motion Loop

Main repo:

- Add private debug task injection or test-only helper for a connected fake U8.
- Add deterministic `transcript` -> `write_text` / `draw_generated` mapping.
- Reuse or port safe `run_path` projection logic where appropriate.
- Send `motion_task` to fake U8.
- Accept `motion_event` progress/done.

Product repo:

- Add a fake LiMa U8 client under `tools/` or `tests/` without changing real
  firmware.

Exit criteria:

- Fake U8 can say `画一个星星`.
- LiMa sends a `run_path` `motion_task`.
- Fake U8 returns `progress` and `done`.
- Tests run without real hardware.

### Phase 3 - U8 Firmware Direct Client

Product repo:

- Add LiMa WebSocket client config for U8.
- Add `hello`, `heartbeat`, `motion_task`, and `motion_event` handling.
- Keep Edge-D UART JSON to U1 unchanged.
- Keep a compile-time fallback to the old Xiaozhi path until direct mode is
  proven.

Main repo:

- Add compatibility tests for U8 direct protocol messages.

Exit criteria:

- U8 firmware build passes.
- Fake or emulator U8 direct protocol test passes.
- No real hardware claim is made yet.

### Phase 4 - Real Device Safety Smoke

Hardware-gated:

- Confirm emergency stop, stop, pause, and home behavior.
- Run `get_device_info`.
- Run a very small square or star path.
- Verify progress and done event return to LiMa.

Exit criteria:

- Real U8/U1 device evidence is recorded.
- Any hardware limitation is recorded before expanding task scope.

### Phase 5 - Audio and TTS

Main repo:

- Add audio stream framing.
- Add ASR adapter through existing LiMa routing/provider stack.
- Add TTS response framing.

Product repo:

- Add U8 direct audio upload and TTS playback path for LiMa direct mode.

Exit criteria:

- Voice command reaches transcript.
- Transcript drives deterministic command mapping.
- TTS or text confirmation returns to U8.

### Phase 6 - Remove Xiaozhi Runtime Dependency

Product repo:

- Make LiMa direct mode the default runtime path.
- Keep migration docs for the old Xiaozhi path only if useful.
- Remove or quarantine Xiaozhi runtime config from production instructions.
- Follow `docs/superpowers/plans/2026-05-24-xiaozhi-server-deprecation-removal.md`
  for the gated deprecation, migration inventory, quarantine, and removal
  sequence.

Main repo:

- Record product endpoint ownership in `docs/ONLINE_DISTRIBUTIONS.md` if a VPS
  route is exposed.

Exit criteria:

- `esp32S_XYZ` can run the target product path without `xiaozhi-server`.
- Main LiMa submodule pointer is advanced to the verified product commit.

## Safety Gates

Do not claim release readiness until these gates pass:

- device authentication cannot be bypassed;
- unknown `device_id` cannot claim another active session;
- malformed messages return stable errors;
- `run_path` is bounded by workspace, length, feed, point count, and estimated
  duration;
- `stop` and `estop` have priority over queued drawing/writing work;
- real hardware smoke proves small-path motion safely;
- provider credentials, device secrets, OTA signing keys, and VPS secrets are
  never committed.

## Verification Matrix

Main LiMa:

```powershell
cd D:\GIT
D:\GIT\venv\Scripts\python.exe -m py_compile server.py routes\device_gateway.py
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway*.py -q --ignore=active_model
```

Product repo:

```powershell
cd D:\GIT\esp32S_XYZ
python tools/validate_schemas.py
python tools/check_gpio.py
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest tools.fake_u1.tests.test_app -v
python -m unittest tools.fake_device_server.tests.test_app -v
python -m unittest tools.fake_ai.tests.test_app -v
```

Firmware build commands must be added after confirming the exact U8 build
environment on the local machine.

## Open Questions

1. Device authentication format:
   - shared per-device token;
   - signed challenge;
   - or device certificate later.
2. Whether first direct U8 firmware should support text-only transcript frames
   before audio streaming.
3. Whether write/draw projection should live first in LiMa, first in
   `esp32S_XYZ`, or temporarily in both while contracts stabilize.
4. Where production device endpoint should live:
   - `wss://chat.donglicao.com/device/v1/ws`;
   - or a separate device subdomain later.

## Recommended First Implementation Slice

Build Phase 1 and the text-only part of Phase 2 first:

1. `/device/v1/health`;
2. `/device/v1/ws`;
3. `hello` / `heartbeat` / stable errors;
4. fake U8 transcript frame;
5. deterministic `写你好` and `画一个星星` mapping;
6. fake U8 receives a bounded `motion_task`.

This proves the LiMa-native device route without touching real firmware or real
hardware.

## Implementation Progress

### 2026-05-24 Phase 1 / Text Fake U8 Slice

Implemented in the main LiMa repo:

- `device_gateway/protocol.py`: protocol version, uplink validation, stable
  error frames, `hello_ack`, and ack helpers.
- `device_gateway/auth.py`: per-device token parsing from `LIMA_DEVICE_TOKENS`.
- `device_gateway/sessions.py`: in-memory active WebSocket session registry.
- `device_gateway/intent.py`: deterministic `write_text`, `draw_generated`,
  `home`, `pause`, `resume`, `stop`, and `get_device_info` command mapping.
- `device_gateway/safety.py`: conservative workspace, feed, point-count, and
  path validation.
- `device_gateway/tasks.py`: deterministic transcript-to-`run_path`
  `motion_task` projection for fake U8 tests.
- `routes/device_gateway.py`: `/device/v1/health` and `/device/v1/ws`.
- `routes/device_gateway.py`: private HTTP fallback/debug routes
  `/device/v1/events` and `/device/v1/tasks`.
- `server.py`: registers the device gateway router.
- `tests/test_device_gateway_protocol.py` and
  `tests/test_device_gateway_routes.py`: fake U8 hello, heartbeat, transcript,
  bounded `motion_task`, `motion_event` ack coverage, private HTTP event ingest,
  and private debug task creation.

Compatibility notes:

- Device authentication is independent from LiMa private/provider API keys.
- Uplink `motion_event` accepts both LiMa `device_id` and esp32S_XYZ-style
  `session_id` compatibility.
- Supported phases include `accepted`, `queued`, `running`, `progress`, `done`,
  `failed`, `cancelled`, `rejected`, and `stopped`.
- This is not yet a real U8 firmware or hardware release. Real-device claims
  still require U8 direct firmware mode and U8/U1 safety smoke.

### 2026-05-24 HTTP Fallback / Debug Slice

Implemented in the main LiMa repo:

- `POST /device/v1/events`: private HTTP fallback for `motion_event`,
  `device_info`, and `self_check` uplink tests.
- `POST /device/v1/tasks`: private debug transcript-to-`motion_task` injection.
  If a WebSocket session is active, the task is sent immediately; otherwise it
  is returned as queued test evidence.

Verification:

```powershell
cd D:\GIT
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py -q --ignore=active_model
```

Result: 15 passed.

### 2026-05-24 Concurrency And Multi-Device Slice

Implemented in the main LiMa repo:

- `device_gateway/sessions.py`: thread-safe session registry plus per-session
  async send lock so concurrent HTTP task injection and WebSocket responses do
  not write to the same device socket at the same time.
- `device_gateway/tasks.py`: thread-safe task store, deterministic unique task
  IDs, per-device pending queues, task dispatched/queued state updates, and
  queue counters.
- `routes/device_gateway.py`: `/device/v1/tasks` now truly queues tasks when a
  device is offline and flushes that device's pending tasks after successful
  `hello`.
- `/device/v1/health` now reports aggregate pending task count.

Verification:

```powershell
cd D:\GIT
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py tests\test_device_gateway_concurrency.py -q --ignore=active_model
```

Result: 19 passed.

### 2026-05-24 HA-Ready Store Boundary Slice

Implemented in the main LiMa repo:

- `device_gateway/store.py`: explicit `DeviceTaskStore` protocol and default
  `InMemoryDeviceTaskStore` for local/dev/test runs.
- `device_gateway/tasks.py`: task helpers now dereference the currently
  installed store module at call time, so tests and future Redis/Postgres
  stores can replace the backing store without stale references.
- `routes/device_gateway.py`: `/device/v1/health` now reports task-store
  backend metadata:
  - `backend`;
  - `shared_across_processes`.
- `tests/test_device_gateway_concurrency.py`: regression coverage proves task
  creation, queue state, and snapshots use a replaced store instance.
- `tests/test_device_gateway_store.py`: direct store contract coverage for
  event snapshots, FIFO requeue, per-device isolation, and concurrent task IDs.
- Task dispatch now tracks per-session in-flight tasks and requeues unsent or
  unacknowledged tasks after synchronous send failure or disconnect.
- Device `hello` drains all currently pending task batches instead of stopping
  after the first 16-task batch.
- `motion_event` is treated as the first device-side task acknowledgement and
  clears the task from that session's in-flight table.

Current production meaning:

- In-memory store supports one LiMa process with many concurrent device
  sessions and requests.
- Multi-process, multi-machine, or VPS HA deployment must run with either:
  - sticky WebSocket routing plus a shared task/event store;
  - or an external session owner/broker design before non-sticky routing.
- Redis/Postgres can be added behind `DeviceTaskStore` without changing route
  handlers or device protocol frames.

Verification:

```powershell
cd D:\GIT
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_device_gateway_protocol.py tests\test_device_gateway_routes.py tests\test_device_gateway_concurrency.py tests\test_device_gateway_store.py -q --ignore=active_model
```

Result: 28 passed.

### 2026-05-24 Product Fake LiMa U8 Slice

Implemented in `esp32S_XYZ`:

- `tools/fake_lima_u8/app.py`: fake U8 client script for LiMa `/device/v1/ws`.
- `tools/fake_lima_u8/tests/test_app.py`: in-memory transport tests covering
  hello, heartbeat, transcript, `motion_task`, and `motion_event` progress/done.
- `tools/README.md`: fake tool entry point and dependency boundary.

Product revision:

```text
78a62c9 test: add fake lima u8 client
```

Verification:

```powershell
cd D:\GIT\esp32S_XYZ
python -m py_compile tools\fake_lima_u8\app.py
python -m unittest tools.fake_lima_u8.tests.test_app -v
python -m unittest tools.fake_device_server.tests.test_app tools.fake_ai.tests.test_app tools.fake_u1.tests.test_app -v
python tools\validate_schemas.py
```

Results:

- fake LiMa U8: 5 passed;
- existing fake U1/device-server/AI suite: 31 passed;
- schemas: `validated=62 passed=62 failed=0`.

### 2026-05-25 Public Route And Redis HA Slice

Implemented in the main LiMa repo and deployed on VPS:

- `https://chat.donglicao.com/device/v1/*` is public through nginx and guarded
  by per-device tokens.
- `device_gateway/redis_store.py` provides Redis-backed task IDs, task
  snapshots, motion events, and per-device pending queues.
- `device_gateway/notifier.py` provides Redis pub/sub task-available
  notifications so the router process that owns a local WebSocket session can
  drain tasks created by another process.
- VPS production health reports Redis task store and Redis session bus.
- Redis is bound to loopback and public `6379` is part of the online
  distribution port-guard smoke.

Verification:

- focused Device Gateway suite: `31 passed`;
- agent-task plus Device Gateway subset: `45 passed`;
- public fake U8 WebSocket loop passed;
- cross-process temp-router smoke passed;
- online distribution smoke: `12/12`.

Detailed evidence lives in
`docs/superpowers/plans/2026-05-25-lima-device-gateway-ha.md`.
