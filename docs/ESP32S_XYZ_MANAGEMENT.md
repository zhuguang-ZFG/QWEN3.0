# esp32S_XYZ Management

> Updated: 2026-06-10

## Purpose

`esp32S_XYZ` is a first-class downstream LiMa product distribution. It contains
the dual ESP32-S3 board project, firmware baselines, Xiaozhi/manager services,
device schemas, monitoring, fake-device tools, and hardware evidence.

The main LiMa repository manages it through the `esp32S_XYZ` submodule because
LiMa will serve as the AI/backend control plane for the product, but the device
project must keep its own source history and release flow.

LiMa is also authorized to perform deep optimization and evidence-backed
refactoring inside the product repository when that is the right way to improve
backend integration, reliability, testability, or hardware-release readiness.
The optimization process is tracked in `docs/ESP32S_XYZ_OPTIMIZATION_ROADMAP.md`.

## Boundary

LiMa owns:

- model routing, AI backend selection, memory, safety policy, and backend
  health;
- VPS-hosted public/private endpoints used by the product;
- API-key and provider-secret custody;
- cross-repository integration records and release evidence;
- the pinned `esp32S_XYZ` revision used for LiMa compatibility.

`esp32S_XYZ` owns:

- U1 motor MCU firmware and U8 AI MCU firmware;
- Edge-A/B/C/D device schemas and examples;
- Xiaozhi server, manager API, manager web/mobile, and product-specific ops;
- hardware validation, provisioning, OTA, self-check, monitoring, and release
  evidence;
- fake U1/device/AI test tools used before real-device verification.

## Repository Entry

| Path | Type | Remote | Branch |
|---|---|---|---|
| `esp32S_XYZ` | Git submodule | `https://github.com/zhuguang-ZFG/esp32S_XYZ.git` | `main` |

Current pinned revision:

```text
a8d98e3 feat: accept route policy in motion task schemas
```

## Integration Model

Use a contract-first integration:

1. Keep LiMa Server as the backend control plane for model routing, AI tasks,
   memory, safety, and externally hosted endpoints.
2. Keep `esp32S_XYZ` as the product implementation for firmware, device
   protocol, manager API/mobile/web, and hardware release evidence.
3. Any LiMa-facing product change must state which contract changed:
   chat/LLM, image/vector generation, voice/ASR/TTS, content safety, OTA
   planning, device telemetry, monitoring, or task orchestration.
4. If a contract changes both sides, commit and push `esp32S_XYZ` first, then
   update the main LiMa submodule pointer plus matching LiMa docs/tests.
5. Do not copy provider credentials, device secrets, VPS passwords, cert
   private keys, or production API keys between repositories.

For cloud-side model selection, provider admission, AI drawing/writing task
families, fallback behavior, and device-aware routing rules, use
`docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md`.

## Refactor Authority

LiMa may modify `D:\QWEN3.0\esp32S_XYZ` directly when working on this product.
Allowed work includes:

- code-quality fixes and test hardening;
- manager API, Xiaozhi server, mobile/web, fake-device, schema, and ops
  refactors;
- product-side adapters for LiMa-hosted AI, voice, image/vector, safety,
  telemetry, and task orchestration;
- documentation, runbook, and CI improvements;
- submodule pointer updates in the main LiMa repository after the product repo
  change is committed and pushed.

Gated work still requires explicit release evidence: production VPS changes,
OTA behavior changes, provisioning behavior changes, hardware motion execution,
secret rotation, cert/key handling, and any destructive hardware action.

## Verification

Before advancing the submodule pointer for product/backend integration, use the
product repository CI-equivalent checks that match the touched area:

```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools/validate_schemas.py
python tools/check_gpio.py
python tools/test_check_gpio.py -v
python -m unittest tools.tests.test_check_gpio -v
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest tools.fake_u1.tests.test_app -v
python -m unittest tools.fake_device_server.tests.test_app -v
python -m unittest tools.fake_ai.tests.test_app -v
python -m unittest tools.fake_lima_u8.tests.test_app -v
python -m unittest tests.ci.test_fake_integration -v
```

For manager API changes:

```powershell
cd D:\QWEN3.0\esp32S_XYZ\server\xiaozhi-esp32-server\main\manager-api
mvn test
```

For manager mobile changes:

```powershell
cd D:\QWEN3.0\esp32S_XYZ\server\xiaozhi-esp32-server\main\manager-mobile
corepack pnpm install --frozen-lockfile --ignore-scripts
corepack pnpm run type-check
corepack pnpm run build:mp-weixin
```

For LiMa backend changes that affect this product, also verify the relevant
main-repo backend tests and public/private endpoint smokes, then record the
evidence in `STATUS.md`, `docs/LIMA_MEMORY.md`, and `progress.md`.

## Operational Records

When this product starts using a LiMa-hosted backend endpoint, record it in:

- `docs/ONLINE_DISTRIBUTIONS.md` for public/private endpoint ownership;
- `infra/vps/` for sanitized nginx/systemd snapshots if VPS services change;
- `STATUS.md` for the short operational snapshot;
- `docs/LIMA_MEMORY.md` for durable cross-session context;
- `progress.md` for chronological closure evidence.

## LiMa Direct Device Gateway Evidence

The product repo now includes `tools/fake_lima_u8/`, a deterministic fake U8
client for LiMa `/device/v1/ws`.

Current fake U8 scope:

- sends `hello` with `protocol=lima-device-v1`;
- sends `heartbeat`;
- sends text `transcript`;
- expects a LiMa `motion_task` with `capability=run_path`;
- emits `motion_event` `progress` and `done`;
- includes both `device_id` and `session_id` on motion events for compatibility
  with existing Edge-C conventions.

The CLI imports the optional `websockets` package only when connecting to a
real LiMa server. Unit tests use an in-memory transport so product CI can verify
the protocol script without adding a network dependency.

Latest LiMa backend evidence:

- `https://chat.donglicao.com/device/v1/health` reports Redis-backed task store
  and Redis session bus.
- Public fake U8 smoke completed against
  `wss://chat.donglicao.com/device/v1/ws`.
- Cross-process delivery was verified by creating a task on a private temp
  router while the device WebSocket stayed connected to the public main router.
- LiMa device tasks now include `route_policy` metadata for `device_control`,
  `device_write`, `device_draw`, `device_vector`, and `device_unknown`.
- `esp32S_XYZ` Edge-B and Edge-C `motion_task` schemas accept the same
  `route_policy` contract, and run_path examples include a `device_vector`
  policy.

## Safety Boundary

Treat real hardware, OTA, provisioning, voiceprint, image generation,
vectorization, and motion execution as gated release surfaces. Design-time
tests and fake-device evidence are useful, but they do not replace physical
device verification for release claims.
