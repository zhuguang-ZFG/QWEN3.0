# LiMa Hardware AI Capability Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade LiMa from a generic model router into the intelligent control plane for the ESP32-S3 drawing/writing device, with lower user effort, stronger AI planning, safer motion execution, better diagnosis, and extremely low task failure rate.

**Architecture:** LiMa becomes the cloud "device brain": it owns intent understanding, content generation, task planning, safety validation, device profiles, recovery policy, and observability. The U8 AI MCU owns local interaction, protocol adaptation, buffering, and offline fallback; the U1 motor MCU owns deterministic motion, homing, limits, and emergency stop.

**Tech Stack:** Python 3.10 + FastAPI + Redis/SQLite in LiMa; ESP-IDF for U8; PlatformIO/Grbl_Esp32 for U1; JSON Schema for Edge protocol contracts; Prometheus/outcome ledger for observability; fake U8/U1 integration tests before hardware-in-loop verification.

---

## 1. Product Decision

LiMa should not merely "replace Xiaozhi server". It should absorb the parts that make the hardware intelligent:

- natural language and voice intent planning;
- AI drawing, writing, prompt expansion, style selection, and content safety;
- deterministic task projection into safe `run_path`/`home`/`move_abs`/`self_check` commands;
- device profile, firmware compatibility, calibration, and capability gating;
- task lifecycle, retry, recovery, and operator-visible diagnostics.

The existing `manager-api`/Xiaozhi stack in `esp32S_XYZ` can remain as the business record during migration, but the device intelligence path should converge into LiMa. This keeps the runtime simpler: one Python cloud brain, one U8 interaction MCU, one U1 motion MCU.

## 2. Current Local Evidence

Main LiMa already has a usable first version:

- `/device/v1/health`, `/device/v1/tasks`, `/device/v1/events`, `/device/v1/ws` in `routes/device_gateway.py`.
- `lima-device-v1` validates `hello`, `heartbeat`, `transcript`, `motion_event`, `device_info`, and `self_check` in `device_gateway/protocol.py`.
- `device_gateway/tasks.py` turns transcript text into `write_text`, `draw_generated`, or control capabilities.
- `device_gateway/path_pipeline.py` has deterministic stroke-font and SVG path parsing.
- `device_gateway/path_validator.py` enforces path length, bounds, and feed limits before a task reaches the device.
- Redis-backed task/session delivery exists through `device_gateway/store.py`, `redis_store.py`, and `notifier.py`.

The product firmware repo already contains the right raw material:

- `esp32S_XYZ/firmware/u1-grbl/` is U1 motor firmware based on Grbl_Esp32.
- `esp32S_XYZ/firmware/u8-xiaozhi/` is U8 AI MCU firmware based on ESP-IDF/Xiaozhi.
- `esp32S_XYZ/docs/schemas/edge_a..edge_d/` already defines the four protocol edges.
- `esp32S_XYZ/tools/fake_lima_u8/` can smoke LiMa `/device/v1/ws`.
- `esp32S_XYZ/tools/fake_device_server/` maps `run_path` to `PATH_BEGIN` / `PATH_SEG` / `PATH_END`.
- `esp32S_XYZ/docs/AI生图与矢量化方案.md` proves the drawing pipeline shape: image generation -> skeletonization -> path tracing -> RDP -> path optimization -> device execution.
- `esp32S_XYZ/docs/U1-Grbl适配说明.md` documents X + dual Y + Z, homing, hard limits, soft limits, and the GPIO46 X step risk.

## 3. External Reference Lessons

Use these repositories as design references, not as code to copy blindly:

| Project | Lesson for LiMa | Apply As |
|---|---|---|
| `espressif/esp-idf` | Treat ESP-IDF as the production baseline for networking, OTA, NVS, watchdogs, logging, and partition discipline. | U8 firmware changes stay ESP-IDF-native and build-verifiable. |
| `esphome/esphome` | Declarative device capability/configuration beats hand-coded per-device behavior for fleet usability. | Add LiMa device profile manifests and compatibility gates. |
| `Aircoookie/WLED` | Consumer ESP devices need friendly setup, OTA, JSON API, presets, and self-recovery paths. | Add local fallback presets, OTA state, and a simple device diagnostics surface. |
| `bdring/FluidNC` | ESP32 motion controllers benefit from Grbl-derived planning plus machine configuration separation. | Keep U1 motion deterministic and move product semantics to LiMa/U8. |
| `gnea/grbl` and Grbl_Esp32 | Motion planning, soft limits, hard limits, feed hold, cycle start, and status polling are safety primitives. | Never bypass U1 safety; LiMa validates before dispatch and U1 validates again. |
| `Klipper3d/klipper` | Host/MCU split works when the host plans and observes while the MCU executes time-critical motion. | LiMa plans and simulates; U1 executes deterministic segments; U8 bridges state. |
| `espressif/esp-sr` | Wake word, VAD, and command recognition can reduce cloud round trips for common commands. | U8 can handle `stop`, `pause`, `resume`, `home`, and wake locally when models fit. |
| `espressif/esp-rainmaker` | Provisioning, cloud control, OTA, and device parameters should be productized, not ad hoc. | Adopt device lifecycle concepts without adding another cloud. |

## 4. Target Capability Model

LiMa should expose a small set of user-facing intents and compile them into device-safe task plans:

| Layer | Capability | Owner | Required Behavior |
|---|---|---|---|
| L4 Account | login, bind, transfer, primary controller, RMA | manager-api first, LiMa later | Durable ownership, audit, no device secrets in clients. |
| L3 User Intent | write poem, draw animal, copy photo, practice character, self-check | LiMa | AI expands user text into a structured plan with safety and age/content filters. |
| L2 Device Task | `write_text`, `draw_generated`, `draw_asset`, `run_path`, `home`, `pause`, `resume`, `stop`, `self_check` | LiMa + U8 | JSON task with idempotency key, profile version, max runtime, preview artifact, and rollback hint. |
| L1 Motion | `HOME`, `MOVE`, `PATH_BEGIN`, `PATH_SEG`, `PATH_END`, `ESTOP`, `GET_STATUS` | U1 | Deterministic execution, buffer credits, error code, final position, and emergency stop. |

Success means a child or parent can say "画一只猫，简单一点" and the system can:

1. infer drawing mode and age-appropriate style;
2. generate or select a drawable asset;
3. convert it to a bounded path;
4. simulate and estimate duration;
5. ask for confirmation only when risk is high;
6. dispatch to the currently compatible device;
7. recover from disconnect or buffer failure without duplicate drawing;
8. explain the failure in plain Chinese when recovery is impossible.

## 5. New LiMa Architecture

```text
-------------------+      +---------------------------+
| Mini App / Voice  | ---> | LiMa Smart Device API     |
+-------------------+      | routes/device_intel.py    |
                           +-------------+-------------+
                                         |
                           +-------------v-------------+
                           | Device Intelligence Core  |
                           | - planner                 |
                           | - safety validator        |
                           | - asset/vector pipeline   |
                           | - simulator               |
                           | - profile store           |
                           | - recovery policy         |
                           +-------------+-------------+
                                         |
                           +-------------v-------------+
                           | Device Gateway            |
                           | /device/v1/ws, MQTT       |
                           | Redis task/session bus    |
                           +-------------+-------------+
                                         |
                 WSS/MQTT motion_task    |
                                         v
                           +-------------+-------------+
                           | U8 AI MCU                 |
                           | - voice/UI interaction    |
                           | - task queue              |
                           | - U1 UART transaction     |
                           | - local offline fallback  |
                           +-------------+-------------+
                                         |
                  Edge-D UART @{json}\n  |
                                         v
                           +-------------+-------------+
                           | U1 MOTOR MCU              |
                           | - Grbl motion             |
                           | - homing/limits/ESTOP     |
                           | - status/error telemetry  |
                           +---------------------------+
```

## 6. Protocol Evolution

Keep `lima-device-v1` running. Add `lima-device-v2` as an opt-in capability negotiated at `hello`.

### 6.1 Uplink `hello` Extension

```json
{
  "type": "hello",
  "protocol": "lima-device-v2",
  "device_id": "dev_001",
  "fw_rev": "u8-0.3.0",
  "u1_fw_rev": "u1-0.2.0",
  "hw_rev": "dlc-motor-control-p1",
  "profile_rev": "p1-2026-06-09",
  "capabilities": ["run_path", "home", "self_check", "offline_asset", "buffer_credit"],
  "workspace_mm": {"x": 200, "y": 200, "z": 20},
  "limits": {"max_points": 800, "max_feed": 1800, "supports_crc": true},
  "request_id": "req_..."
}
```

### 6.2 Downlink `motion_task` Extension

```json
{
  "type": "motion_task",
  "task_id": "task-000001",
  "device_id": "dev_001",
  "idempotency_key": "sha256:...",
  "capability": "run_path",
  "source": "voice",
  "profile_rev": "p1-2026-06-09",
  "expires_at": "2026-06-09T13:30:00Z",
  "params": {
    "feed": 900,
    "path": [{"x": 10, "y": 10, "z": 0}],
    "preview_svg": "<svg .../>",
    "estimated_ms": 42000,
    "max_runtime_ms": 90000,
    "safety_policy": "home_required"
  }
}
```

### 6.3 Motion Event Extension

```json
{
  "type": "motion_event",
  "device_id": "dev_001",
  "task_id": "task-000001",
  "phase": "progress",
  "progress": {
    "pct": 34,
    "segment_index": 122,
    "buffer_free": 6,
    "position": {"x": 80.2, "y": 41.5, "z": 0},
    "u1_state": "Run"
  }
}
```

## 7. Server Implementation Units

Create focused modules instead of expanding `device_gateway/tasks.py`.

| File | Responsibility |
|---|---|
| `device_intelligence/schemas.py` | Dataclasses and JSON-safe structures for device profile, task plan, safety result, and recovery action. |
| `device_intelligence/profile_store.py` | SQLite-backed profile, firmware, workspace, calibration, and capability lookup. |
| `device_intelligence/planner.py` | Converts user intent/transcript into a structured L3/L2 task plan. |
| `device_intelligence/asset_pipeline.py` | Text/SVG/image-to-path orchestration and preview artifact creation. |
| `device_intelligence/safety.py` | Bounds, point count, feed, homing, runtime, content, and firmware compatibility checks. |
| `device_intelligence/simulator.py` | Dry-run path execution estimate: bounds, pen-up distance, duration, and risk score. |
| `device_intelligence/recovery.py` | Maps U1/U8 errors to retry, re-home, stop, ask-user, or service actions. |
| `routes/device_intelligence.py` | Private/admin APIs for plan preview, submit, task status, and recovery decision. |

Keep the existing `device_gateway/` package as transport and task delivery. It should consume already-planned tasks, not own AI planning.

## 8. Firmware Implementation Units

### 8.1 U8 AI MCU

Modify the existing Zhuguang board files under:

- `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/u1_protocol_client.*`
- `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/motion_executor.*`
- `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/motion_event_emitter.*`
- `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.cc`

Required changes:

- add `lima-device-v2` hello fields from real U1 `GET_DEVICE_INFO`;
- add task idempotency cache so reconnect does not duplicate a drawing;
- add U1 UART transaction sequence numbers and optional CRC field;
- add buffer-credit aware `PATH_SEG` streaming instead of fire-and-wait only;
- add local voice shortcuts for `stop`, `pause`, `resume`, `home`, and `status`;
- add offline fallback for built-in assets and cached last-good task;
- emit richer progress with U1 state, position, segment index, and buffer status.

### 8.2 U1 MOTOR MCU

Modify the existing U1 Grbl_Esp32 adaptation under:

- `esp32S_XYZ/firmware/u1-grbl/Grbl_Esp32/src/Machines/dlc_motor_control_p1.h`
- Edge-D command parser files discovered during implementation
- `esp32S_XYZ/firmware/u1-grbl/wokwi_sim/wokwi_sim.ino` for simulation coverage

Required changes:

- keep hard limits, soft limits, homing, feed hold, and ESTOP as non-bypassable;
- add `GET_STATUS` details: homed, machine state, position, alarm code, buffer free, current task id;
- add `PATH_BEGIN` validation: total segments, feed, workspace, profile revision;
- add `PATH_SEG` ack with segment index and buffer credit;
- add `PATH_END` terminal result with final position and execution summary;
- add stable business error codes mapped to LiMa recovery policy;
- verify GPIO46 X step behavior before release or record a hardware redesign decision.

## 9. Reliability Targets

| Metric | Target | Measurement |
|---|---:|---|
| Invalid task reaches U8 | 0 | LiMa safety tests and schema tests. |
| Invalid motion reaches U1 | 0 | U8 parser tests and U1 Edge-D tests. |
| Duplicate task after reconnect | 0 | Fake U8 reconnect test with same idempotency key. |
| Terminal event missing | < 0.1% | Prometheus ratio: tasks without done/failed/cancelled after timeout. |
| Simple local control latency | < 200 ms | U8 local command path for stop/pause/resume/status. |
| Voice-to-path cloud latency | < 5 s p50 | LiMa planner + asset pipeline telemetry. |
| Recovery explanation coverage | 100% for known U1/U8 errors | `device_intelligence/recovery.py` table tests. |

## 10. Two-VPS Deployment Strategy

LiMa has two VPS nodes:

- Alibaba Cloud VPS: primary production control plane.
- JDCloud VPS: standby, probe, canary, and release-evidence node.

Do not run device WebSocket active-active until task/session ownership is provably single-writer. Device long connections and motion tasks are stateful; dual-primary dispatch can duplicate drawings or split task state.

### 10.1 Alibaba Cloud Responsibilities

- Serve `https://chat.donglicao.com`.
- Run production LiMa FastAPI, Device Gateway, Redis task/session bus, model routing, task planning, and ops metrics.
- Own production `.env`, API secrets, provider keys, and public nginx.
- Accept production device WebSocket/MQTT sessions.
- Dispatch production motion tasks.

### 10.2 JDCloud Responsibilities

- Run synthetic external smokes against Alibaba public endpoints:
  - `/health`
  - `/device/v1/health`
  - fake U8 WSS
  - authenticated task creation
  - Prometheus scrape when enabled
- Run provider and backend probes outside the production process.
- Host OTA canary manifests and firmware artifacts for internal/test devices.
- Keep a cold-standby LiMa runtime with sanitized env, deploy scripts, and restore runbook.
- Store release evidence: fake-device logs, OTA install results, smoke transcripts, and hardware-in-loop summaries.
- Verify Alibaba from outside its own network before release closure.

### 10.3 Failover Rule

Failover is manual until Redis/session replication and task ownership are explicitly designed. The safe failover contract is:

1. stop production task dispatch on Alibaba;
2. snapshot Redis/device task state;
3. restore or intentionally drain state on JDCloud;
4. switch DNS or nginx upstream;
5. require devices to reconnect and re-hello;
6. reject duplicate idempotency keys already terminal on Alibaba.

## 11. Xiaozhi Service Migration Decisions

Migrate contracts and high-value product capabilities from `esp32S_XYZ/server/xiaozhi-esp32-server`, not the entire runtime.

### 11.1 Migrate First

| Source Area | Why It Matters | LiMa Target |
|---|---|---|
| AppV2 device binding and activation | Required for consumer product ownership. | `device_identity/` or `device_intelligence/profile_store.py` with SQLite first. |
| Runtime admission and disposed-device rejection | Prevents retired, transferred, or repaired devices from connecting. | `device_intelligence/admission.py`, called from device `hello`. |
| Task approval and primary session | Lets parent approve risky voice tasks. | `device_intelligence/approval.py` and private routes. |
| Firmware release plan and install result | Enables safe OTA rollout and rollback. | `device_ota/manifest.py`, `device_ota/releases.py`. |
| Self-check history | Turns hardware diagnosis into product support evidence. | `device_intelligence/self_check.py`. |
| Voiceprint cache and family members | Enables child/parent/guest policy. | `device_identity/voiceprint.py` with privacy gates. |
| ASR/VAD/TTS provider interfaces | Saves integration work and performance comparison. | Keep LiMa routing; port only provider contracts and performance tests. |
| Correct words / per-device config | Improves ASR tolerance and personalization. | Profile-scoped prompt/config overlay. |
| Content safety and audit rows | Required for child/family product scenarios. | LiMa safety ledger and retention policy. |

### 11.2 Do Not Migrate Initially

- full Java `manager-api` runtime;
- full Vue `manager-web`;
- digital-human demo;
- Home Assistant generic plugin set;
- every ASR/TTS provider at once;
- generic agent/template/memory management that is not device-specific.

### 11.3 Migration Rule

For every Xiaozhi capability:

1. copy the contract and tests first;
2. reimplement minimal Python in LiMa;
3. keep old Xiaozhi service as reference until LiMa passes fake-device and product tests;
4. remove or bypass the old service only after public/private smoke and hardware evidence.

## 12. High-Yield Additions

These items are not optional "nice-to-have" features; they are the highest leverage ways to make the device feel intelligent, simple, and low-error.

### 12.1 Device Shadow

Add a device shadow model:

```json
{
  "device_id": "dev_001",
  "desired": {"fw_rev": "u8-0.3.1", "profile_rev": "p1-2026-06-09"},
  "reported": {"fw_rev": "u8-0.3.0", "online": true, "homed": false},
  "delta": {"fw_rev": "u8-0.3.1", "home_required": true},
  "updated_at": "2026-06-09T13:00:00Z"
}
```

This makes reconnect, config sync, OTA, profile rollout, and device diagnosis deterministic.

### 12.2 OTA Rings

OTA must be ring-based:

1. `dev`
2. `internal`
3. `one_real_device`
4. `five_percent`
5. `thirty_percent`
6. `stable`

JDCloud owns canary verification; Alibaba owns stable production dispatch.

### 12.3 Hardware Self-Check Wizard

First bind and support flows should run:

- U8 boot and Wi-Fi check;
- U8 to U1 UART check;
- U1 `GET_DEVICE_INFO`;
- limit switch state check;
- homing check;
- pen lift/drop check;
- bounded 20 mm square dry run;
- final result stored as support evidence.

### 12.4 Offline Local Controls

U8 should handle without cloud AI:

- stop;
- pause;
- resume;
- home;
- status;
- draw built-in simple assets;
- replay last safe cached task only when idempotency and user confirmation allow it.

### 12.5 Asset and Template Library

Prebuilt assets are a business feature and a reliability fallback:

- stars, hearts, cats, cards, Chinese practice grids;
- stroke-order templates;
- holiday cards;
- offline-safe icons;
- style packs for children.

When AI generation fails, LiMa should degrade to a known-safe asset, not return a model error.

### 12.6 Vision Feedback

Later hardware revisions with camera support can add:

- paper detection;
- drawing area calibration;
- photo-to-outline;
- post-drawing quality score;
- automatic scale correction.

This is the clearest path from "connected plotter" to "intelligent hardware".

## 13. Personalized Device Intelligence and Memory Layer

Long-term memory is a high-return product capability for a family hardware device. It should not be implemented as generic chat transcript storage. LiMa needs structured, permissioned, device-aware memory that helps the hardware plan better, fail less, and feel more personal.

### 13.1 Memory Types

| Memory Type | Scope | Example | Product Value |
|---|---|---|---|
| `family_profile` | family/account | parent account, child member, approval policy | Enables child-safe behavior and family permissions. |
| `user_profile` | member | age band, preferred language, drawing style, favorite themes | Personalizes output with less prompting. |
| `operation_habit` | member + device | common times, common commands, repeated edits, cancellation patterns | Reduces taps and repeated instructions. |
| `device_profile_memory` | device | stable feed, homing status, calibration, recurring U1 errors | Lowers motion failure rate. |
| `task_episode` | task | prompt, generated path stats, result, user feedback | Learns which plans work on real hardware. |
| `safety_memory` | family/member | rejected topics, approval decisions, blocked capabilities | Makes parental policy durable. |
| `procedure_memory` | device model | "for this machine, complex drawings work best under 420 points and feed 800" | Turns experience into repeatable execution recipes. |

### 13.2 Planner Recall Contract

Before LiMa creates a task plan, it recalls memory by:

- `family_id`
- `member_id`
- `device_id`
- `task_type`
- `capability`
- `risk_level`

The planner can use memory to adjust style, point count, feed, approval requirement, prompt wording, asset selection, and recovery hints. Memory can never override hard safety checks.

Example:

```json
{
  "prompt": "simple cute cat line drawing",
  "style": "child_friendly",
  "max_points": 420,
  "feed": 800,
  "approval_required": false,
  "reason": "child user prefers simple animal drawings; this device had limit errors above feed 1000"
}
```

### 13.3 Memory Write Contract

After a terminal task event, LiMa writes only structured facts:

- prompt summary, not raw audio;
- path statistics, not necessarily full path unless needed for debugging;
- success/failure phase;
- U1/U8 error code and recovery action;
- user feedback if explicitly given;
- source event id and confidence.

Every memory row must include:

```json
{
  "memory_id": "mem_...",
  "type": "task_episode",
  "family_id": "fam_...",
  "member_id": "member_...",
  "device_id": "dev_...",
  "source_task_id": "task-000001",
  "confidence": 0.86,
  "ttl_days": 365,
  "created_at": "2026-06-09T13:00:00Z",
  "updated_at": "2026-06-09T13:00:00Z"
}
```

### 13.4 Privacy and Child Safety

- Do not store raw voice by default.
- Do not store full camera images by default.
- Do not cross-recall memories between families.
- Parent-facing UI must support list, delete, export, and disable memory.
- Child-sensitive facts require shorter TTL unless parent explicitly pins them.
- Safety decisions keep provenance: who approved, when, and why.
- Device-health memory can be anonymized for fleet-level learning.

### 13.5 Hermes-Inspired Local Knowledge Shape

Borrow the idea of layered human-readable memory:

- `FAMILY.md` equivalent: household rules, members, permissions.
- `USER.md` equivalent: preferences, style, learning progress.
- `DEVICE.md` equivalent: hardware profile, calibration, recurring failures.
- `PROCEDURES.md` equivalent: successful recipes and recovery playbooks.

The database remains authoritative, but periodic Markdown snapshots are useful for audits, support, and agent handoff.

## 14. Continuous Learning Loop

LiMa should become smarter with use, but only through explicit, inspectable product memory and outcome learning. This is not model fine-tuning by default. It is a closed loop that turns real device usage into safer, more personalized planning.

### 14.1 Learning Loop Contract

```text
user intent
  -> planner creates task
  -> safety validates task
  -> device executes task
  -> U8/U1 reports terminal event
  -> LiMa extracts structured memory
  -> consolidation updates preferences/procedures/device health
  -> next planner recall uses memory for soft personalization
  -> eval checks whether success rate improved
```

### 14.2 What Gets Smarter

| Learning Area | Example | Planner Effect |
|---|---|---|
| User preference | child likes simple animal drawings | choose child-friendly line art and fewer points. |
| Operation habit | family often draws cards at night | show card suggestions at that time. |
| Device health | this device fails above feed 1000 | cap suggested feed lower before safety validation. |
| Task outcome | cat template succeeds, complex tiger fails | prefer proven cat template for similar prompt. |
| Recovery behavior | `E_NOT_HOMED` recovered after `home` twice | auto-suggest home before retry. |
| Family policy | parent rejected internet image tasks | require approval for similar future tasks. |

### 14.3 What Memory May Influence

Memory can influence:

- prompt wording;
- art style;
- template choice;
- point budget below the device cap;
- feed below the device cap;
- approval recommendation;
- suggested recovery action;
- homepage recommendations;
- support diagnosis.

Memory can never override:

- workspace bounds;
- hard/soft limits;
- ESTOP;
- firmware compatibility;
- child safety policy;
- explicit parent rejection;
- OTA block;
- device admission status.

### 14.4 Learning Quality Gates

Every learning change must be measurable:

- success rate by capability;
- failure rate by error code;
- average retries per task;
- terminal-event completeness;
- approval false-positive rate;
- user thumbs-up/down where available;
- support ticket recurrence by device model.

A memory-derived procedure is not auto-applied until it has enough evidence for the same device model or device id.

### 14.5 User Control

Users and parents must be able to:

- view saved memories;
- delete a memory;
- disable memory for the family;
- export memory;
- reset personalization for one device;
- pin an important preference;
- mark a learned assumption as wrong.

### 14.6 Anti-Learning Rules

LiMa must not learn from:

- failed tasks caused by public API outage;
- test/fake devices unless explicitly marked as training evidence;
- raw child audio;
- raw camera images;
- one-off unsafe prompts;
- unverified hardware tests;
- tasks with missing terminal event.

## 15. Additional High-Return Intelligent Directions

### 15.1 Local Wake and Command Classifier

Move the most safety-critical commands closer to the device:

- stop;
- pause;
- resume;
- home;
- status;
- cancel current task.

This can use U8-side wake word / command recognition when model size and ESP32-S3 memory allow it. Cloud AI should not be required for emergency or common control.

### 15.2 Anomaly Detection for Device Health

Use task and telemetry history to detect:

- rising homing failure rate;
- repeated limit hits on one axis;
- UART timeout clusters;
- feed values correlated with failures;
- devices that fail OTA more often than peers;
- drawing duration drifting from simulation estimate.

Start with rule-based detectors in LiMa. Move to ML only after enough labeled failures exist.

### 15.3 Matter-Style Commissioning and Multi-Controller UX

The product should feel like modern smart-home devices:

- QR code pairing;
- short-lived setup token;
- visible bound account/device name;
- primary controller and secondary viewer roles;
- safe transfer flow;
- explicit unbind/factory reset behavior.

Do not adopt Matter as a dependency unless hardware/product strategy requires it. Adopt the user experience principles.

### 15.4 Guided Creation Modes

Add productized creation flows instead of one generic prompt box:

- "练字模式": character, grid, stroke order, repeat count.
- "简笔画模式": object, style, complexity.
- "贺卡模式": theme, recipient, short message, border.
- "照片描线模式": upload image, preview outline, simplify.
- "课堂模式": teacher-selected templates and locked safety settings.

Guided modes reduce prompt ambiguity and model failure rate.

### 15.5 Fleet Learning Without Privacy Leakage

Aggregate only non-personal metrics:

- model + firmware + hardware revision;
- task type;
- path point bucket;
- feed bucket;
- terminal phase;
- error code;
- recovery action;
- duration bucket.

Use this to improve default profiles and procedure memory across devices without copying user content.

### 15.6 Support Copilot

Build an internal operator assistant that reads:

- device shadow;
- recent task episodes;
- U1/U8 error history;
- OTA version;
- self-check evidence;
- known hardware risks.

It returns a support diagnosis and next action. This directly lowers support cost when real devices ship.

## 16. External Non-AI Public API Enrichment Layer

Free public APIs should be used to enrich LiMa's hardware intelligence, not to replace LiMa's own planning and safety logic. The goal is to add real-world context, educational content, seasonal prompts, local conditions, and stable public metadata without paying for additional AI APIs.

### 16.1 Highest-Value Public APIs

| Provider | Type | LiMa Use | Priority |
|---|---|---|---|
| Open-Meteo | Weather, air quality, geocoding, sunrise/sunset | Weather-aware cards, paper/ink humidity hints, seasonal drawing prompts. | P0 |
| Nager.Date | Public holidays | Holiday cards, family reminders, seasonal homepage suggestions. | P0 |
| Wikidata / Wikipedia | Structured public knowledge | Child-friendly facts, poem/author context, educational drawing/writing themes. | P0 |
| Open Library | Book metadata | Reading cards, author facts, book-themed writing/drawing tasks. | P1 |
| NASA Open APIs | Astronomy and public science media | Space cards, astronomy drawing prompts, educational "today in space" content. | P1 |
| OpenStreetMap Nominatim | Geocoding | Coarse location to weather/time/holiday context. | P1 with strict cache and rate limits. |
| REST Countries | Country metadata | Geography learning cards, flag/country theme prompts. | P1 |
| GitHub Releases API | Release metadata | Firmware artifact discovery and mirror sync metadata. | P1, but production OTA must use LiMa-controlled manifests. |
| MusicBrainz | Music metadata | Song/artist context for voice interaction and education. | P2 |
| USGS Earthquake API | Public geoscience data | Geography/science cards and event-based educational prompts. | P2 |
| Wikimedia Commons | Public media metadata | Licensed educational references and public-domain-style assets. | P2 with license filtering. |
| MakeMeAHanzi / KanjiVG / OpenMoji datasets | Public datasets, not runtime APIs | Stroke order, writing practice, symbols, emoji-like offline assets. | P0/P1 as local ingested data. |

### 16.2 Product Experiences Enabled

Examples:

- "今天画什么": combine weather, holiday, user preference, and device capability.
- "节日贺卡": combine Nager.Date, memory, templates, and guided card mode.
- "儿童百科绘画": combine Wikidata/Wikipedia with simple drawing templates.
- "读书卡": combine Open Library with writing and drawing layout.
- "天气安全提示": use humidity/temperature to remind users to check paper and pen.
- "固件发布镜像": use GitHub Releases only as upstream metadata; LiMa signs and serves the actual OTA manifest.

### 16.3 Integration Architecture

Create a provider-neutral package:

```text
external_enrichment/
  __init__.py
  cache.py
  rate_limit.py
  attribution.py
  schemas.py
  providers/
    open_meteo.py
    nager_date.py
    wikidata.py
    open_library.py
    nasa.py
    osm_nominatim.py
    rest_countries.py
    github_releases.py
```

Rules:

- All providers must have timeouts and bounded response sizes.
- All providers must return structured data, not raw API payloads.
- All provider results must be cached with explicit TTL.
- All provider failures degrade gracefully and never fail a device motion task.
- Every external result includes source and attribution fields.
- Every provider uses a clear `User-Agent`.
- Rate limits are enforced locally before request.
- No child raw prompt, raw audio, image, or exact home address is sent to public APIs.

### 16.4 Cache Policy

| Data | TTL |
|---|---:|
| Weather now/hourly | 30 minutes |
| Air quality | 30 minutes |
| Sunrise/sunset | 24 hours |
| Holidays | 30 days |
| Wikidata entity summary | 30 days |
| Open Library book metadata | 30 days |
| NASA APOD metadata | 7 days |
| Nominatim geocode result | 90 days |
| REST Countries | 90 days |
| GitHub release metadata | 1 hour |

### 16.5 Do Not Add

Avoid these initially:

- public translation instances;
- random joke/fact/image APIs;
- third-party QR code generators;
- unaudited public image search APIs;
- high-volume public geocoding without cache;
- any API that requires sending child speech or raw personal content.

## 17. LiMa Service Thickening Roadmap

LiMa should be thickened as a product-grade device cloud, not by adding more user-facing entry points, but by adding durable control-plane and evidence-plane services. These services make every device action observable, repeatable, recoverable, and auditable.

### 17.1 Event-Sourced Task Ledger

Every task should become an append-only event stream:

```text
task_created
task_planned
safety_checked
task_dispatched
device_accepted
u1_started
progress
failed
recovered
done
user_feedback
```

The current task snapshot remains useful for fast reads, but the ledger is the source of truth for replay, support, learning, release evidence, and incident investigation.

### 17.2 Artifact Store

Every task can produce artifacts:

- user intent summary;
- task plan JSON;
- safety report;
- simulation report;
- preview SVG;
- path JSON;
- generated image metadata;
- vectorization metadata;
- U8/U1 terminal result;
- support snapshot;
- user feedback.

Artifacts should be content-addressed where possible and tied to `task_id`, `device_id`, `family_id`, and retention policy.

### 17.3 Unified Policy Engine

Create one policy decision point for:

- content safety;
- child/member permissions;
- parent approval;
- device admission;
- firmware compatibility;
- OTA blocks;
- self-check requirement;
- home requirement;
- external API availability;
- memory usage permission.

The output vocabulary should be stable:

```text
allow
require_approval
reject
require_self_check
require_home
require_ota
degrade_to_asset
```

### 17.4 Workflow Orchestrator

Drawing and writing tasks are long workflows:

```text
intent -> generate -> vectorize -> simulate -> approve -> dispatch -> monitor -> recover -> archive
```

A lightweight orchestrator should own state transitions, retries, and timeouts. It can start with SQLite/Redis and should not require a heavy distributed workflow system for MVP.

### 17.5 Simulation-as-a-Service

Simulation should be a reusable service, not only a helper inside the planner:

- path bounds;
- point count;
- pen-up distance;
- draw distance;
- estimated runtime;
- max jump;
- required homing;
- risk score;
- device-specific feed recommendation.

Every `run_path` should carry the simulation version and simulation report id.

### 17.6 Fault Injection and Chaos Harness

LiMa needs deterministic failure tests:

- U8 disconnect after dispatch;
- U1 UART timeout;
- Redis temporary outage;
- OTA install failure;
- hard limit hit;
- duplicate task id;
- public API timeout;
- model returns malformed SVG;
- task terminal event missing.

The goal is to know how LiMa fails before users do.

### 17.7 Operator Console

The operator console should be utilitarian and evidence-first:

- device online/offline;
- shadow desired/reported/delta;
- recent task ledger;
- latest support bundle;
- OTA ring and install result;
- feature flags;
- capability disable switches;
- recurring error summaries;
- public/JDCloud probe status.

This is not a marketing dashboard. It is a production control surface.

### 17.8 Device Identity and Factory Provisioning

Product readiness requires:

- device unique identity;
- activation code or QR binding;
- factory self-test record;
- token/certificate rotation;
- revoke/dispose/repair states;
- ownership transfer;
- factory reset contract.

Factory provisioning is a release surface and must have test evidence.

### 17.9 Release Gate Service

Each release should collect:

- main repo focused tests;
- product repo schema tests;
- U1 build;
- U8 build;
- fake U8 public smoke;
- fake U1 fault injection;
- JDCloud external probe;
- OTA canary result;
- rollback artifact;
- docs/status update evidence.

Release is blocked when required evidence is missing.

### 17.10 Entitlement and Resource Authorization

Even before monetization, design resource authorization:

- AI generation quota;
- premium font authorization;
- template pack authorization;
- family member role;
- device feature authorization;
- offline asset authorization.

This prevents future subscription/content-pack work from rewriting the task model.

### 17.11 Protocol Version Registry

Maintain one registry for:

- `lima-device-v1`;
- `lima-device-v2`;
- `edge-d-v1`;
- `edge-d-v2`;
- minimum U8 firmware;
- minimum U1 firmware;
- supported capabilities;
- deprecated fields.

New cloud behavior must check this registry before dispatch.

### 17.12 Knowledge Pack System

Make stable content reusable:

- child line-art pack;
- Chinese character practice pack;
- Tang poetry pack;
- holiday card pack;
- English word card pack;
- geometry/math drawing pack.

Knowledge packs are safer and more predictable than pure one-off generation.

### 17.13 Evaluation Bench

Maintain a device task benchmark:

- writing tasks;
- simple drawing tasks;
- complex path tasks;
- recovery tasks;
- offline/disconnect tasks;
- OTA tasks;
- memory personalization tasks;
- external enrichment tasks.

Every planner, vectorizer, gateway, firmware, or policy change should show whether this bench improved or regressed.

## 18. Implementation Tasks

### Task 1: Add Device Intelligence Interfaces

**Files:**
- Create: `device_intelligence/__init__.py`
- Create: `device_intelligence/schemas.py`
- Test: `tests/test_device_intelligence_schemas.py`

- [ ] **Step 1: Create typed plan/profile models**

Define:

```python
@dataclass(frozen=True)
class DeviceProfile:
    device_id: str
    hw_rev: str
    fw_rev: str
    profile_rev: str
    workspace_mm: dict[str, float]
    capabilities: frozenset[str]
    max_points: int
    max_feed: float

@dataclass(frozen=True)
class TaskPlan:
    task_id: str
    device_id: str
    capability: str
    params: dict[str, Any]
    idempotency_key: str
    profile_rev: str
    estimated_ms: int
    risk_score: float
```

- [ ] **Step 2: Add tests for JSON-safe conversion**

Run: `python -m pytest tests/test_device_intelligence_schemas.py -q`

Expected: profile and task plan serialize with sorted deterministic keys, `frozenset` becomes a sorted list, and empty `device_id` is rejected.

### Task 2: Move Planning Out of Transport

**Files:**
- Create: `device_intelligence/planner.py`
- Modify: `device_gateway/tasks.py`
- Test: `tests/test_device_intelligence_planner.py`

- [ ] **Step 1: Keep transcript resolution but return a structured plan request**

The planner maps:

- "回零" -> `home`
- "暂停" -> `pause`
- "继续" -> `resume`
- "停止" -> `stop`
- "状态" -> `get_device_info`
- "写..." -> `write_text`
- drawing prompts -> `draw_generated`

- [ ] **Step 2: Preserve current behavior through `create_task_from_transcript`**

`device_gateway/tasks.py` should call the planner, then the asset pipeline, then safety validation. The public `/device/v1/tasks` response shape remains compatible with v1.

- [ ] **Step 3: Run focused tests**

Run: `python -m pytest tests/test_device_gateway_routes.py tests/test_device_intelligence_planner.py -q`

Expected: existing device gateway tests pass and new planner intent cases pass.

### Task 3: Add Profile-Aware Safety

**Files:**
- Create: `device_intelligence/safety.py`
- Create: `device_intelligence/profile_store.py`
- Modify: `device_gateway/path_validator.py`
- Test: `tests/test_device_intelligence_safety.py`

- [ ] **Step 1: Validate against device profile, not only global constants**

Check:

- every point is inside `workspace_mm`;
- feed is inside profile `max_feed`;
- point count is inside profile `max_points`;
- `run_path` requires `home_required` unless profile says homed state is fresh;
- firmware/profile revision is compatible.

- [ ] **Step 2: Preserve v1 fallback**

If no profile exists, use current constants from `device_gateway/path_validator.py` so old fake devices keep working.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_gateway_path_validator.py tests/test_device_intelligence_safety.py -q`

Expected: v1 validators pass; profile-specific limit tests reject oversize paths before dispatch.

### Task 4: Add Simulation and Risk Scoring

**Files:**
- Create: `device_intelligence/simulator.py`
- Modify: `device_gateway/tasks.py`
- Test: `tests/test_device_intelligence_simulator.py`

- [ ] **Step 1: Estimate path runtime and risk**

The simulator computes:

- total draw distance;
- pen-up travel distance;
- estimated runtime from feed;
- max segment jump;
- risk score from high feed, too many points, long runtime, near-boundary points, and unhomed profile.

- [ ] **Step 2: Store estimates in task params**

Add `estimated_ms`, `path_stats`, and `risk_score` to generated task params. The U8 can display progress expectations and LiMa can alert on outliers.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_intelligence_simulator.py tests/test_device_gateway_routes.py -q`

Expected: deterministic estimates for a square path and no regression in task creation.

### Task 5: Add Recovery Policy

**Files:**
- Create: `device_intelligence/recovery.py`
- Modify: `routes/device_gateway_ws_handlers.py`
- Test: `tests/test_device_intelligence_recovery.py`

- [ ] **Step 1: Map stable errors to actions**

Examples:

- `E_MISSING_PATH` -> reject task, explain "路径为空";
- `E_LIMIT` -> stop and ask user to check paper/axis;
- `E_NOT_HOMED` -> enqueue `home`, then retry once;
- `E_UART_TIMEOUT` -> retry U1 status, then requeue task once;
- `E_ESTOP` -> do not retry, require manual clear.

- [ ] **Step 2: Record terminal recovery hints**

When `motion_event.phase == "failed"`, append `recovery_action` to task snapshot and outcome ledger metadata.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_intelligence_recovery.py tests/test_device_gateway_routes.py -q`

Expected: every known error returns one deterministic recovery action and one Chinese user-facing explanation.

### Task 6: Upgrade U8 Protocol Bridge

**Files:**
- Modify: `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/u1_protocol_client.*`
- Modify: `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/motion_executor.*`
- Modify: `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/test_u8_protocol_logic.cpp`

- [ ] **Step 1: Add sequence and idempotency handling**

Every U1 transaction carries a monotonic `msg_id`; every LiMa task carries `task_id` and `idempotency_key`. U8 stores a short ring buffer of completed keys and returns the prior terminal result when a duplicate appears.

- [ ] **Step 2: Add buffer-credit progress**

`PATH_SEG` ack includes `segment_index` and `buffer_free`; U8 emits these values in `motion_event.progress`.

- [ ] **Step 3: Run product firmware tests**

Run in `esp32S_XYZ`: `make test`

Expected: existing 251 tests remain green and new U8 protocol logic cases pass.

### Task 7: Upgrade U1 Motion Results

**Files:**
- Modify: `esp32S_XYZ/firmware/u1-grbl/Grbl_Esp32/src/Machines/dlc_motor_control_p1.h`
- Modify: Edge-D parser/source files found by `rg "PATH_BEGIN|GET_STATUS|ESTOP" firmware/u1-grbl`
- Modify: `esp32S_XYZ/docs/schemas/edge_d/*.schema.json`
- Test: `esp32S_XYZ/tests/ci/test_edge_d_firmware_static.py`

- [ ] **Step 1: Add richer `GET_STATUS` and terminal result fields**

Include `homed`, `state`, `position`, `alarm`, `buffer_free`, and `current_task_id`.

- [ ] **Step 2: Enforce duplicate safety**

U1 rejects a new `PATH_BEGIN` while a different task is active unless the current task is terminal or stopped.

- [ ] **Step 3: Run product static and schema tests**

Run in `esp32S_XYZ`: `python tools/validate_schemas.py && python -m unittest tests.ci.test_edge_d_firmware_static -v`

Expected: schema examples validate and static checks cover the new fields.

### Task 8: Add End-to-End Fake Device Reliability Tests

**Files:**
- Modify: `esp32S_XYZ/tools/fake_lima_u8/app.py`
- Modify: `esp32S_XYZ/tools/fake_device_server/app.py`
- Create or modify: `tests/test_device_gateway_reliability.py`

- [ ] **Step 1: Simulate disconnect and reconnect**

Fake U8 disconnects after receiving a task, reconnects with the same device id, and receives no duplicate execution when the original task was terminal.

- [ ] **Step 2: Simulate U1 failure classes**

Fake U1 injects `E_NOT_HOMED`, `E_LIMIT`, `E_UART_TIMEOUT`, and `E_ESTOP`; LiMa records deterministic recovery actions.

- [ ] **Step 3: Run focused reliability tests**

Run: `python -m pytest tests/test_device_gateway_reliability.py -q`

Expected: all injected failures terminate with either recovered success or explicit non-retryable failure.

### Task 9: Add Device Shadow Store

**Files:**
- Create: `device_intelligence/shadow.py`
- Create: `tests/test_device_intelligence_shadow.py`
- Modify: `routes/device_gateway_ws_handlers.py`

- [ ] **Step 1: Store desired/reported/delta state**

`hello`, `heartbeat`, `device_info`, `self_check`, and `motion_event` update reported state. Admin/profile updates write desired state. Delta is computed as desired values that differ from reported values.

- [ ] **Step 2: Return delta on hello ack**

When U8 sends `hello`, LiMa returns `hello_ack` plus the pending config delta for firmware/profile/config sync.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_intelligence_shadow.py tests/test_device_gateway_routes.py -q`

Expected: shadow deltas are deterministic and v1 hello ack remains compatible.

### Task 10: Add OTA Release Plan

**Files:**
- Create: `device_ota/__init__.py`
- Create: `device_ota/releases.py`
- Create: `device_ota/manifest.py`
- Create: `routes/device_ota.py`
- Test: `tests/test_device_ota.py`

- [ ] **Step 1: Implement release ring selection**

Given `device_id`, `hw_rev`, `fw_rev`, and ring membership, return no update or a signed manifest with target firmware, checksum, size, and rollback policy.

- [ ] **Step 2: Record install result**

U8 reports `install_started`, `install_succeeded`, or `install_failed`; LiMa freezes rollout when failure ratio exceeds the configured ring threshold.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_ota.py -q`

Expected: dev/internal/canary/stable rings select correct versions and failure ratio freezes rollout.

### Task 11: Port Xiaozhi Runtime Admission and Approval

**Files:**
- Create: `device_intelligence/admission.py`
- Create: `device_intelligence/approval.py`
- Modify: `routes/device_gateway_ws_handlers.py`
- Create: `tests/test_device_admission_approval.py`

- [ ] **Step 1: Reject inactive devices during hello**

Admission denies disposed, transferred-away, unbound, firmware-blocked, or maintenance-locked devices before session registration.

- [ ] **Step 2: Gate risky voice tasks**

Voice tasks with high risk score, large runtime, unsafe content, or child speaker identity require approval before dispatch.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_admission_approval.py tests/test_device_gateway_routes.py -q`

Expected: denied devices never enter the session registry and approval-required tasks are queued without reaching U8.

### Task 12: Add JDCloud Probe and Canary Flow

**Files:**
- Create: `scripts/check_device_gateway_public.py`
- Create: `docs/ops/DEVICE_GATEWAY_TWO_VPS_RUNBOOK.md`
- Modify: `tests/test_ci_gates.py`

- [ ] **Step 1: Add public fake-U8 probe script**

The script checks Alibaba public `/device/v1/health`, opens WSS as fake U8, submits a private task, and verifies terminal motion event.

- [ ] **Step 2: Document failover and canary gates**

The runbook records Alibaba primary, JDCloud probe/canary role, manual failover steps, and OTA ring promotion evidence.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_ci_gates.py -q`

Expected: CI gate recognizes the probe script and runbook paths without requiring public network access in unit tests.

### Task 13: Add Structured Device Memory

**Files:**
- Create: `device_memory/__init__.py`
- Create: `device_memory/schemas.py`
- Create: `device_memory/store.py`
- Create: `tests/test_device_memory_store.py`

- [ ] **Step 1: Define memory record types**

Support `family_profile`, `user_profile`, `operation_habit`, `device_profile_memory`, `task_episode`, `safety_memory`, and `procedure_memory`.

- [ ] **Step 2: Enforce scope isolation**

Reads require matching `family_id`; cross-family recall returns no rows even when `device_id` or prompt text is similar.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_memory_store.py -q`

Expected: create, recall, TTL filtering, delete, export, and cross-family isolation pass.

### Task 14: Add Memory Recall to Planning

**Files:**
- Create: `device_memory/recall.py`
- Modify: `device_intelligence/planner.py`
- Modify: `device_intelligence/safety.py`
- Create: `tests/test_device_memory_planner_recall.py`

- [ ] **Step 1: Recall relevant memories before task planning**

Recall by `family_id`, `member_id`, `device_id`, `capability`, and `task_type`. Return a bounded list sorted by confidence and recency.

- [ ] **Step 2: Apply memory only to soft choices**

Memory may adjust style, feed under the safety cap, max points under the profile cap, prompt wording, asset choice, and approval recommendation. Memory cannot override workspace, hard limits, firmware blocks, or child safety policy.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_memory_planner_recall.py tests/test_device_intelligence_safety.py -q`

Expected: preference memory personalizes a task, device failure memory lowers feed, and hard safety still wins.

### Task 15: Extract Memories From Terminal Task Events

**Files:**
- Create: `device_memory/extractor.py`
- Modify: `routes/device_gateway_ws_handlers.py`
- Create: `tests/test_device_memory_extractor.py`

- [ ] **Step 1: Extract structured task episodes**

On `done`, `failed`, or `cancelled`, write a `task_episode` with task id, source capability, path stats, terminal phase, error code, recovery action, and confidence.

- [ ] **Step 2: Extract procedure candidates**

When the same device model succeeds repeatedly with similar path stats and feed, create or update a `procedure_memory` candidate with confidence below auto-apply threshold until enough evidence accumulates.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_memory_extractor.py tests/test_device_gateway_routes.py -q`

Expected: terminal events produce structured memories, failed tasks do not store raw prompt/audio, and repeated successes raise procedure confidence.

### Task 16: Add Support Copilot Snapshot

**Files:**
- Create: `device_support/snapshot.py`
- Create: `routes/device_support.py`
- Create: `tests/test_device_support_snapshot.py`

- [ ] **Step 1: Build support snapshot**

For a device id, return shadow state, latest firmware, self-check summary, recent terminal tasks, top recurring errors, memory-derived procedures, and recommended next action.

- [ ] **Step 2: Keep it private and redacted**

Require admin token and redact member names, raw prompts, voice data, and image data.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_support_snapshot.py -q`

Expected: support snapshot contains actionable hardware diagnosis and no raw child/user content.

### Task 17: Add Continuous Learning Consolidation

**Files:**
- Create: `device_memory/consolidation.py`
- Create: `device_memory/quality_gates.py`
- Modify: `device_memory/store.py`
- Create: `tests/test_device_memory_consolidation.py`

- [ ] **Step 1: Consolidate task episodes into stable memories**

Repeated successful task episodes update `operation_habit`, `user_profile`, or `procedure_memory` only when confidence and evidence count pass thresholds.

- [ ] **Step 2: Reject unsafe learning sources**

Consolidation ignores fake devices unless marked as training evidence, raw child audio, raw camera images, missing terminal events, public API outages, and unverified hardware tests.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_memory_consolidation.py -q`

Expected: repeated successes create higher-confidence procedure memory, single failures do not overfit, and anti-learning rules block unsafe sources.

### Task 18: Add User Memory Controls

**Files:**
- Create: `routes/device_memory.py`
- Modify: `device_memory/store.py`
- Create: `tests/test_device_memory_routes.py`

- [ ] **Step 1: Add private memory list/delete/export endpoints**

Routes require account/admin authorization and support listing by family, member, device, and memory type.

- [ ] **Step 2: Add disable/reset controls**

Support disabling memory for a family, resetting one device's personalization, pinning a preference, and marking a learned assumption as wrong.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_memory_routes.py -q`

Expected: delete/export/disable/reset work and cross-family access is rejected.

### Task 19: Add External Non-AI Enrichment Layer

**Files:**
- Create: `external_enrichment/__init__.py`
- Create: `external_enrichment/cache.py`
- Create: `external_enrichment/rate_limit.py`
- Create: `external_enrichment/attribution.py`
- Create: `external_enrichment/schemas.py`
- Create: `external_enrichment/providers/open_meteo.py`
- Create: `external_enrichment/providers/nager_date.py`
- Create: `tests/test_external_enrichment.py`

- [ ] **Step 1: Implement provider interface and cache**

Every provider returns a typed result with `source`, `fetched_at`, `ttl_seconds`, `attribution`, and `payload`.

- [ ] **Step 2: Add Open-Meteo and Nager.Date first**

Open-Meteo powers weather/air/sunrise context. Nager.Date powers holiday cards. Both providers must be optional and must return cached fallback data when the public API is unavailable.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_external_enrichment.py -q`

Expected: cache TTL, provider fallback, attribution, user-agent construction, and no-raw-child-content guard pass without network access.

### Task 20: Connect Enrichment to Device Planner

**Files:**
- Modify: `device_intelligence/planner.py`
- Modify: `device_intelligence/schemas.py`
- Create: `tests/test_device_planner_enrichment.py`

- [ ] **Step 1: Add optional context input**

Planner accepts an `enrichment_context` object with weather, holiday, location label, and educational facts. Missing context behaves exactly like current planner behavior.

- [ ] **Step 2: Use context only for soft choices**

Weather and holiday context may affect prompt wording, template choice, preview label, and suggestions. It cannot override safety, approval, workspace, firmware, or feed limits.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_planner_enrichment.py tests/test_device_intelligence_safety.py -q`

Expected: rainy weather changes suggestion text, holiday context chooses a card template, and hard safety remains authoritative.

### Task 21: Add Event Ledger and Artifact Store

**Files:**
- Create: `device_ledger/__init__.py`
- Create: `device_ledger/events.py`
- Create: `device_ledger/store.py`
- Create: `device_artifacts/__init__.py`
- Create: `device_artifacts/store.py`
- Modify: `routes/device_gateway_ws_handlers.py`
- Create: `tests/test_device_ledger_artifacts.py`

- [ ] **Step 1: Append task events**

Every task create, plan, dispatch, motion event, recovery, and terminal result appends one immutable ledger event.

- [ ] **Step 2: Store task artifacts**

Store plan JSON, safety report, simulation report, preview SVG, path stats, and terminal result under a task id with retention metadata.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_ledger_artifacts.py tests/test_device_gateway_routes.py -q`

Expected: replay reconstructs task state, artifacts are linked to task id, and duplicate event ids are rejected.

### Task 22: Add Unified Policy Engine and Protocol Registry

**Files:**
- Create: `device_policy/__init__.py`
- Create: `device_policy/engine.py`
- Create: `device_policy/decisions.py`
- Create: `device_protocol_registry.py`
- Modify: `device_intelligence/safety.py`
- Create: `tests/test_device_policy_protocol_registry.py`

- [ ] **Step 1: Define policy decision vocabulary**

Implement `allow`, `require_approval`, `reject`, `require_self_check`, `require_home`, `require_ota`, and `degrade_to_asset`.

- [ ] **Step 2: Gate dispatch with protocol compatibility**

Dispatch checks device protocol, U8 firmware, U1 firmware, profile revision, and capability support before task delivery.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_policy_protocol_registry.py tests/test_device_intelligence_safety.py -q`

Expected: old firmware is blocked from new capabilities, child approval rules are enforced, and policy decisions are deterministic.

### Task 23: Add Workflow Orchestrator and Simulation Service

**Files:**
- Create: `device_workflow/__init__.py`
- Create: `device_workflow/state.py`
- Create: `device_workflow/orchestrator.py`
- Modify: `device_intelligence/simulator.py`
- Create: `tests/test_device_workflow.py`

- [ ] **Step 1: Model long-running task states**

Workflow states include `created`, `planned`, `simulated`, `waiting_approval`, `ready_to_dispatch`, `dispatched`, `running`, `recovering`, `terminal`.

- [ ] **Step 2: Store simulation report id on task plans**

Every `run_path` plan references a simulation report id and simulator version.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_workflow.py tests/test_device_intelligence_simulator.py -q`

Expected: workflow transitions are valid, invalid transitions fail, and simulation reports are reusable.

### Task 24: Add Release Gate and Fault Injection Harness

**Files:**
- Create: `scripts/device_release_gate.py`
- Create: `tests/test_device_release_gate.py`
- Modify: `esp32S_XYZ/tools/fake_lima_u8/app.py`
- Modify: `esp32S_XYZ/tools/fake_device_server/app.py`
- Create: `docs/ops/DEVICE_RELEASE_GATE.md`

- [ ] **Step 1: Implement release evidence checklist**

The gate checks required local test commands, fake-device probes, JDCloud public probe evidence, OTA canary evidence, and rollback artifact paths.

- [ ] **Step 2: Add deterministic fault injection modes**

Fake U8/U1 support disconnect, timeout, duplicate task id, limit error, malformed terminal event, and OTA failure modes.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_device_release_gate.py tests/test_device_gateway_reliability.py -q`

Expected: release gate blocks missing evidence and fault injection cases produce deterministic recovery or explicit failure.

## 19. Verification Ladder

Execute in this order:

1. Main repo focused tests: `python -m pytest tests/test_device_gateway*.py tests/test_device_intelligence*.py -q`.
2. Main repo full safe gate: `python scripts/run_pre_commit_check.py --full`.
3. Product repo schema and fake tests: `python tools/validate_schemas.py`, `python -m unittest discover -s tests -p "test_*.py" -v`, and fake tool tests.
4. U1/U8 firmware build in `esp32S_XYZ`: `make build-u1`, `make build-u8`.
5. Public LiMa fake U8 smoke against `wss://chat.donglicao.com/device/v1/ws`.
6. Hardware-in-loop smoke with physical ESP32-S3 board, no pen installed.
7. Hardware-in-loop smoke with pen installed and bounded 20 mm square.
8. Full drawing/write task smoke with recovery evidence.

No production release claim is valid until step 8 completes. OTA promotion also requires JDCloud canary evidence. Memory-enabled releases also require delete/export/privacy tests, consolidation tests, and anti-learning tests. External-enrichment releases require offline-cache tests and public API failure tests. Service-thickening releases require ledger replay, policy decision, workflow transition, and release-gate tests.

## 20. Acceptance Criteria

- LiMa can preview and submit a structured device plan before dispatch.
- Invalid path, bad feed, stale profile, unsupported firmware, and unhomed state are blocked before U8 receives a task.
- U8 can safely resume after reconnect without duplicate drawing.
- U1 reports enough state for LiMa to diagnose `not homed`, `limit hit`, `buffer issue`, `ESTOP`, and `UART timeout`.
- Every terminal task has `done`, `failed`, `cancelled`, or `rejected`.
- Every known failure has a deterministic Chinese explanation and recovery action.
- Device `stop`/`pause`/`resume`/`status` works locally on U8 without waiting for cloud AI.
- The old `lima-device-v1` fake U8 continues to work during migration.
- Alibaba remains the only production dispatcher until dual-primary task ownership is designed.
- JDCloud proves public health, fake U8, and OTA canary before production rollout.
- Xiaozhi service migration preserves contracts and tests without importing the whole runtime.
- Planner uses family/user/device memory for soft personalization while hard safety checks remain authoritative.
- Parents can view, delete, export, and disable memory.
- Terminal task events produce structured memory without raw audio or raw camera content.
- Fleet learning uses anonymized buckets only.
- External non-AI APIs are accessed only through `external_enrichment`.
- Public API outages never fail motion dispatch.
- Every external enrichment result has cache, attribution, timeout, and rate-limit behavior.
- Planner uses enrichment only for soft personalization and education context.
- LiMa gets measurably smarter through structured memory: higher success rate, fewer repeated errors, and fewer repeated user instructions.
- Learned memories can be inspected, corrected, deleted, disabled, and exported.
- Memory-derived procedures are not auto-applied until confidence and evidence thresholds pass.
- Memory never overrides hard safety or parent policy.
- Every task has replayable ledger events.
- Every generated or dispatched task has linked artifacts.
- Policy decisions are centralized and testable.
- Workflow state transitions are explicit.
- Release gate blocks missing evidence.
- Fault injection covers core device failure modes.

## 21. Hardware Verification Boundaries

The current design assumes the board is ESP32-S3 based on `esp32S_XYZ` documentation and firmware paths. Before flashing or motion testing, confirm:

- exact board revision and flash size;
- U8/U1 UART pins and baud;
- stepper driver current limits and thermal behavior;
- limit switch polarity and debounce;
- GPIO46 suitability for X step pulse on the physical board;
- OTA partition layout and rollback requirement;
- whether production security enables secure boot, flash encryption, or disabled JTAG.

Design and fake tests can proceed without physical hardware. Motion execution, OTA, provisioning, current/thermal behavior, and GPIO46 stability require hardware evidence.

## 22. Source References

- Local: `routes/device_gateway.py`
- Local: `device_gateway/protocol.py`
- Local: `device_gateway/tasks.py`
- Local: `device_gateway/path_pipeline.py`
- Local: `esp32S_XYZ/docs/架构定稿-v2.md`
- Local: `esp32S_XYZ/docs/AI生图与矢量化方案.md`
- Local: `esp32S_XYZ/docs/U1-Grbl适配说明.md`
- Local: `esp32S_XYZ/server/xiaozhi-esp32-server/main/xiaozhi-server/core/websocket_server.py`
- Local: `esp32S_XYZ/server/xiaozhi-esp32-server/main/xiaozhi-server/config/manage_api_client.py`
- Local: `esp32S_XYZ/server/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml`
- External: https://github.com/espressif/esp-idf
- External: https://github.com/esphome/esphome
- External: https://github.com/Aircoookie/WLED
- External: https://github.com/bdring/FluidNC
- External: https://github.com/gnea/grbl
- External: https://github.com/Klipper3d/klipper
- External: https://github.com/espressif/esp-sr
- External: https://github.com/espressif/esp-rainmaker
- External: https://docs.aws.amazon.com/iot/latest/developerguide/iot-device-shadows.html
- External: https://docs.aws.amazon.com/iot/latest/developerguide/iot-jobs.html
- External: https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-devguide-device-twins
- External: https://github.com/eclipse-hawkbit/hawkbit
- External: https://github.com/mem0ai/mem0
- External: https://arxiv.org/abs/2504.19413
- External: https://arxiv.org/abs/2604.04853
- External: https://arxiv.org/abs/2603.16171
- External: https://www.edgeimpulse.com/
- External: https://csa-iot.org/all-solutions/matter/
- External: https://open-meteo.com/
- External: https://date.nager.at/
- External: https://www.wikidata.org/wiki/Help:Data_access
- External: https://www.mediawiki.org/wiki/API:Main_page
- External: https://openlibrary.org/developers/api
- External: https://api.nasa.gov/
- External: https://operations.osmfoundation.org/policies/nominatim/
- External: https://restcountries.com/
- External: https://musicbrainz.org/doc/MusicBrainz_API
- External: https://earthquake.usgs.gov/fdsnws/event/1/
