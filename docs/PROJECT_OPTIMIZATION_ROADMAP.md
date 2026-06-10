# LiMa Project Optimization Roadmap

> Updated: 2026-06-10
> Scope: whole-project documentation and implementation roadmap after the
> strategic pivot from personal coding assistant backend to AI smart-device
> cloud service.

## Current Position

LiMa is now a multi-backend AI routing server and device cloud control plane.
The current priority is no longer adding more generic chat features. The
priority is making AI drawing/writing machine workflows reliable, observable,
and safe while keeping the existing OpenAI/Anthropic-compatible API usable.

The latest device-routing slice is closed:

- `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md` defines drawing/writing
  model roles, admission gates, switching rules, device-aware inputs, safety,
  observability, and release verification.
- `device_gateway/model_routing.py` classifies device tasks into
  `device_control`, `device_write`, `device_draw`, `device_vector`, and
  `device_unknown`.
- `device_gateway/tasks.py` attaches `route_policy` metadata to generated
  `motion_task` payloads.
- `esp32S_XYZ` commit `a8d98e3` accepts `route_policy` in Edge-B and Edge-C
  `motion_task` schemas and examples.
- Main repo commit `423bf3e` advances the product submodule pointer to that
  schema-compatible revision.

No VPS restart or physical firmware flash was performed for that slice because
the runtime behavior was metadata/schema/docs only.

## Operating Principles

1. Device safety beats model cleverness.
2. Provider admission is evidence-based, not availability-based.
3. Deterministic routes are first choice for control, plain writing, and known
   assets.
4. AI models may plan, generate, explain, and recover, but validated geometry is
   the only authority for motion.
5. Secrets remain in LiMa or approved server-side secret storage, never in
   firmware, client apps, product examples, or browser-visible config.
6. Cross-repo changes land product repo first, then LiMa docs/tests/submodule
   pointer.
7. Full deploy claims require VPS smoke evidence; hardware-release claims also
   require fake-device and physical-device evidence.

## Optimization Streams

| Stream | Owner Area | Current State | Next Outcome |
|---|---|---|---|
| Device task routing | `device_gateway/` | Route roles and `route_policy` exist | Fake U8 consumes and reports route policy |
| Drawing/writing model policy | `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md` | Cloud-side policy documented | First dated image/vector admission report |
| Product firmware/schema | `esp32S_XYZ/` | Edge-B/C schemas accept route policy | U8 adapter validates and logs route policy |
| Motion safety | `path_validator.py`, product U1/U8 | Validator exists, physical gate still separate | Simulator and fake-device release gate become mandatory |
| General LLM routing | `routing_engine.py`, `router_v3.py`, `routing_selector.py` | Existing chat/coding route engine remains active | Device roles stop depending on generic chat pool behavior |
| Observability | `observability/`, device ledger/artifacts | Metrics and device artifacts exist | Route decision to terminal motion trace is queryable |
| CI and release | `scripts/run_pre_commit_check.py`, deploy scripts | Main focused gates pass; full gates vary by baseline | Separate device, server, and product release gates |
| Documentation | `docs/README.md`, `STATUS.md`, `progress.md` | Latest device routing recorded | Docs index becomes the starting point for all active work |

## Phase 1: Stabilize Device Route Contracts

Goal: every device task can explain why it selected its route and what the
device is allowed to do with it.

Steps:

1. Keep `route_policy` on all `motion_task` paths, including policy-blocked
   and validation-failed paths.
2. Add fake U8 assertions that route roles are received, logged, and surfaced
   in terminal `motion_event` evidence.
3. Add product-side schema examples for `device_control`, `device_write`,
   `device_draw`, and `device_vector`, not only `run_path`.
4. Record route role, capability, model role, and validation result in device
   artifacts.
5. Reject unknown or firmware-incompatible route policies before U1 motion
   execution.

Required verification:

```powershell
python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py -q
cd D:\QWEN3.0\esp32S_XYZ
python tools\validate_schemas.py
python -m unittest tests.ci.test_validate_schemas -v
python -m unittest tools.fake_lima_u8.tests.test_app -v
```

Promotion rule: do not change U1 motion firmware from this phase alone. U1
changes wait until fake U8 and simulator evidence show the contract is stable.

## Phase 2: Admit AI Drawing/Writing Models By Role

Goal: separate device model roles from generic chat/coding route pools.

Steps:

1. Create a dated admission report under `docs/model_admission/` for
   drawing/writing fixtures.
2. Evaluate at least these role classes:
   intent parser, text planner, prompt enhancer, image generator, vectorizer,
   vision analyzer, and recovery explainer.
3. Record backend id, provider, model id, fixture count, pass count, latency,
   failure modes, admission decision, and rollback rule.
4. Keep direct LLM-to-SVG experimental until geometry fixtures prove bounded
   paths and stable point counts.
5. Add route preferences for device roles without moving unverified providers
   into first-tier generic chat/coding pools.

Required verification:

```powershell
python -m pytest tests/test_device_gateway_model_routing.py -q
python -m pytest tests/test_routing_engine.py -q --tb=short
python scripts/run_pre_commit_check.py --full
```

Promotion rule: a backend can enter a hot drawing/writing route only when its
dated evidence is linked from `docs/FREE_MODEL_ROUTING_STATUS.md` or a
role-specific admission report.

## Phase 3: Make Device Profiles First-Class Routing Inputs

Goal: route decisions account for firmware, hardware, workspace, and point
limits before model selection.

Steps:

1. Extend the device shadow/profile record with `fw_rev`, `u1_fw_rev`,
   `hw_rev`, `workspace_mm`, `capabilities`, `profile_rev`, and
   `limits.max_points`.
2. Make missing profile data conservative: lower point count, smaller scale,
   preset routes preferred, generated drawing downgraded or approval-gated.
3. Add compatibility checks before dispatch to hardware.
4. Add per-device sticky route memory only after safety/profile compatibility
   checks pass.
5. Record simplification decisions in the task artifact and recovery
   explanation.

Required verification:

```powershell
python -m pytest tests/test_device_gateway_routes.py tests/test_device_gateway_store.py -q
python -m pytest tests/test_p1_4_device_stability_gate.py -q
```

Promotion rule: profile-aware simplification is allowed; silent geometry repair
is not allowed. The task must record what was simplified.

## Phase 4: Harden The General LLM Route While Keeping Device Work Isolated

Goal: preserve the public OpenAI/Anthropic-compatible API without letting
generic chat regressions control device safety.

Steps:

1. Keep `routing_engine.route()` as the authoritative chat/coding route entry.
2. Keep `smart_router.py` and `router_http.py` as compatibility/legacy surfaces
   only; new production callers use the current route engine and `http_caller`.
3. Split route tests by surface: chat/coding, device, ops, product integration.
4. Keep provider health/cooldown/budget failures visible in logs and metrics.
5. Avoid promoting local Windows proxy backends to VPS-first routes unless the
   VPS process can reach them through the documented topology.

Required verification:

```powershell
python -m pytest tests/test_routing_engine.py tests/test_http_caller.py -q
python scripts/run_ruff_check.py
```

Promotion rule: any provider pool change needs focused route-order tests and
fresh smoke evidence for the actual deployment topology.

## Phase 5: Build A Release Gate For AI-To-Motion

Goal: release claims are based on an end-to-end trace from user request to
terminal motion event.

Steps:

1. Add a release checklist for `/device/v1/health`, fake U8 WebSocket,
   control, writing, generated drawing, validation failure, disconnect
   recovery, and terminal event replay.
2. Make fake U8/U1 tests mandatory before physical-device verification.
3. Add a physical-device evidence template that records board revision,
   firmware revision, workspace, material, prompt, generated artifact hash,
   path point count, runtime estimate, terminal result, and operator notes.
4. Store release evidence in `STATUS.md`, `progress.md`, and
   `docs/LIMA_MEMORY.md`; long reports go under `docs/release_evidence/`.
5. Keep deployment evidence separate from hardware evidence. A healthy VPS does
   not prove safe motion.

Required verification:

```powershell
python scripts/run_pre_commit_check.py --full
python scripts/deploy_unified.py
curl -sf https://chat.donglicao.com/health
curl -sf https://chat.donglicao.com/device/v1/health
```

Promotion rule: public production readiness requires both server smoke and
hardware gate evidence for any motion-affecting release.

## Documentation System

Use this source hierarchy:

| Document | Role |
|---|---|
| `docs/README.md` | Entry point and document map |
| `STATUS.md` | Current project state and latest closeout |
| `progress.md` | Chronological execution evidence |
| `docs/LIMA_MEMORY.md` | Durable cross-session memory |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | Production route ownership |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md` | Device model-routing policy |
| `docs/ESP32S_XYZ_MANAGEMENT.md` | Product submodule boundary |
| `docs/PROJECT_OPTIMIZATION_ROADMAP.md` | Active whole-project roadmap |

Documentation rules:

- Update `docs/README.md` when a new active document becomes an entry point.
- Update `STATUS.md` when a slice is closed or operational status changes.
- Update `progress.md` with verification evidence before commit.
- Update `docs/LIMA_MEMORY.md` for cross-session facts that future agents must
  not rediscover.
- Archive or remove stale execution reports after their facts are merged into
  durable docs.

## Immediate Next Coding Tasks

1. Product fake U8 consumes `route_policy`.
   Expected files: `esp32S_XYZ/tools/fake_lima_u8/app.py`,
   `esp32S_XYZ/tools/fake_lima_u8/tests/test_app.py`, schema examples.
2. LiMa device artifacts record route evidence.
   Expected files: `device_gateway/tasks.py`, `device_artifacts/`,
   `tests/test_device_gateway_model_routing.py`.
3. Device model admission report scaffold.
   Expected files: `docs/model_admission/YYYY-MM-DD-device-drawing-writing.md`
   and a focused eval script or reproducible command list.
4. Device profile routing inputs.
   Expected files: `device_gateway/profiles.py`, `device_gateway/tasks.py`,
   matching route and store tests.
5. AI-to-motion release evidence template.
   Expected file: `docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`.

## Risks To Watch

| Risk | Why It Matters | Control |
|---|---|---|
| Generic chat pool drives motion tasks | Chat quality is not motion safety | Device route roles and admission gates |
| Direct SVG from LLM bypasses validator | Invalid geometry can damage output or hardware | Validator and simulator remain authoritative |
| Firmware consumes unknown route policy | U8/U1 behavior becomes non-deterministic | Schema compatibility and fake U8 assertions |
| Docs diverge from code | Agents make wrong routing/deploy decisions | Code wins; docs updated in same slice |
| VPS smoke skipped after runtime changes | Local-only success hides production failure | Real `chat.donglicao.com` smoke for deploy claims |
| Full test baseline drifts | Agents misread unrelated failures as slice failures | Focused gates plus recorded full-gate baseline |

## Closeout Standard

A project slice is complete only when:

1. Relevant focused tests passed.
2. Formatting/lint/diff checks passed or the known unrelated blocker is
   recorded.
3. Product-repo checks passed when product contracts changed.
4. VPS smoke evidence exists when runtime deployment changed.
5. Hardware evidence exists when physical motion behavior changed.
6. `STATUS.md`, `progress.md`, and `docs/LIMA_MEMORY.md` contain the durable
   result.
7. Only related files are staged, committed, and pushed.
