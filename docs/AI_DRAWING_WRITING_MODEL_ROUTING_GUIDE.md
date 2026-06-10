# AI Drawing/Writing Machine Model Routing Guide

> Updated: 2026-06-10
> Scope: LiMa cloud-side model management, routing policy, and admission gates for the `esp32S_XYZ` AI drawing/writing machine.

## Purpose

LiMa is the cloud control plane for `esp32S_XYZ`. The product repository owns
firmware, device schemas, hardware evidence, fake devices, and release flow.
LiMa owns model routing, provider custody, task planning, safety policy, memory,
observability, and public/private endpoints.

This document defines how LiMa should choose, switch, admit, and retire AI
models when serving AI drawing and writing devices. It is intentionally more
specific than the general router documents because a bad model choice can
produce unsafe motion, wasted material, user-visible failure, or device damage.

## Source Of Truth

Use these files together:

| Concern | Source |
|---|---|
| Production request pipeline | `docs/REQUEST_PIPELINE_AUTHORITY.md` |
| Route engine design | `docs/ROUTING_ENGINE_DESIGN.md` |
| Backend/model catalog | `docs/MODEL_CATALOG.md` |
| Free model evidence and policy | `docs/FREE_MODEL_ROUTING_STATUS.md` |
| Product submodule boundary | `docs/ESP32S_XYZ_MANAGEMENT.md` |
| Device protocol | `docs/device_protocol_alignment.md` |
| Product firmware and fake devices | `esp32S_XYZ/` |
| Live route pools | `router_v3.py` |
| Live route ranking | `routing_selector.py` |
| Device task projection | `device_gateway/tasks.py` |
| Device intent parsing | `device_gateway/intent.py` |
| Path generation/validation | `device_gateway/path_pipeline.py`, `device_gateway/path_validator.py` |

When a document and code disagree, production behavior follows code. Update this
document when changing route pools, provider admission, device task contracts,
or the model requirements for drawing/writing tasks.

## Ownership Boundary

LiMa cloud owns:

- intent understanding and user prompt normalization;
- AI model selection and backend failover;
- image, vector, text, and safety model admission;
- task planning into `write_text`, `draw_generated`, `draw_asset`, `run_path`,
  `home`, `pause`, `resume`, `stop`, `self_check`;
- content safety, geometry safety, policy gating, simulation, approval, and
  recovery;
- task ledger, preview artifacts, operator diagnostics, metrics, and feedback.

`esp32S_XYZ` owns:

- U8 AI MCU firmware behavior and LiMa protocol adapter;
- U1 motor MCU deterministic motion execution;
- Edge-A/B/C/D schemas and product manager services;
- GPIO, homing, limits, OTA, provisioning, fake U8/U1 tools, and physical
  hardware evidence;
- product release artifacts and submodule history.

Any change that affects both repositories must land in this order:

1. Update `esp32S_XYZ` schema/firmware/fake-device behavior.
2. Commit and push the product repository.
3. Update LiMa code/docs/tests.
4. Advance the LiMa submodule pointer.
5. Record verification evidence in `STATUS.md`, `progress.md`, and
   `docs/LIMA_MEMORY.md`.

## Product Task Taxonomy

LiMa should classify drawing/writing requests into device task families before
choosing a model.

| Family | Examples | Model Need | Default Path |
|---|---|---|---|
| Control | stop, pause, resume, home, device info | No LLM | Deterministic parser -> device gateway |
| Plain writing | write "Happy Birthday", copy short text | No image model; optional text polish | `write_text` -> stroke font/path |
| Creative writing | poem, blessing, child-friendly sentence | Text model with JSON-safe output | text planner -> `write_text` |
| Simple drawing | star, heart, house, cat outline | Asset library first, then image/vector | preset SVG -> `run_path` |
| Generated drawing | draw a cat in simple line-art style | Image model + vectorizer or proven SVG provider | image -> skeleton/vector -> `run_path` |
| Uploaded image copy | trace this photo | Vision/image preprocessing + vectorizer | image normalization -> vector -> `run_path` |
| Practice/education | write Chinese character, stroke practice | Text/layout model plus template rules | template asset -> `run_path` |
| Ambiguous command | "make it nicer", "draw something cute" | Low-risk planner only | gated LLM planner -> confirm if needed |
| Unsafe/unbounded | huge picture, adult/violent prompt, full-page scribble | Reject or require approval | policy block before dispatch |

Routing starts from the task family, not from the provider name. A backend is
only eligible if it has passed the evidence gate for that family.

## Model Role Classes

Use role-specific model admission instead of one global "best model" ranking.

| Role | Required Properties | Non-goals |
|---|---|---|
| Intent parser | Deterministic JSON, low latency, conservative rejection | Creative text generation |
| Text planner | Chinese/English quality, controllable length, JSON schema discipline | Motion geometry |
| Prompt enhancer | Produces short image prompts, child-safe, style-aware | Final task authority |
| Image generator | Line-art quality, fast small output, low artifact rate | Direct motion output |
| Vision analyzer | Identifies drawable structure and safety issues | Artistic invention |
| Vectorizer | Deterministic geometry, bounded point count, preview artifact | Semantic reasoning |
| Motion validator | No AI dependency; enforces bounds/feed/point limits | "Fixing" unsafe output silently |
| Recovery explainer | Clear user/operator explanation from known error codes | Retrying hardware blindly |

The current product evidence favors `qwen-image-2.0` at `512x512` for generated
line-art because it was fast enough and vectorized well in the product repo.
Direct LLM-to-SVG should remain non-primary until a repeatable geometry eval
shows accurate, bounded, device-safe paths.

## Routing Decision Matrix

| Input Signal | Primary Route | Fallback | Block Condition |
|---|---|---|---|
| Exact control command | `device_gateway.intent` deterministic parser | none | unknown device/session |
| Short plain text | deterministic `write_text` path | text model only for formatting when requested | text too long for workspace |
| Ambiguous natural language | deterministic parser first; LLM planner only if `LIMA_DEVICE_LLM_PLANNER=1` | ask for clarification or write literal text | low confidence plus risky capability |
| Drawing from common shape | local/preset SVG asset | generated image route | asset exceeds workspace/point limits |
| Drawing from prompt | admitted image model -> vectorizer -> validator | admitted fallback image model; then simple preset/text fallback | unsafe prompt, vectorization failure, path too large |
| Uploaded photo | vision/preprocess -> vectorizer -> validator | ask user to crop/simplify | face/privacy policy or too complex |
| Chinese character practice | template/stroke asset route | text planner for instructions only | missing font/template coverage |
| Device reports low capability | simpler profile and lower point/feed limits | queue until compatible | required capability absent |
| Backend degraded/dead | `routing_selector.select()` removes or downranks | next admitted backend | no admitted backend for role |
| Hardware high risk | simulator + approval | reduce scale/feed/points | policy denies or approval missing |

## Admission Gates

No new model may enter a hot drawing/writing route without dated evidence.

### Gate A: Provider And Secret Custody

- Provider key stays in LiMa or approved VPS secret storage.
- No provider token is copied into `esp32S_XYZ`, firmware, mobile clients, or
  browser-visible config.
- Backend config names must be stable and searchable in `backends_registry.py`
  or the approved admission overlay.

### Gate B: Functional Fit

Run role-specific fixtures before promotion:

| Role | Minimum Fixture |
|---|---|
| Intent parser | 20 commands: control, write, draw, ambiguous, reject |
| Text planner | 20 JSON outputs: valid schema, length bounded, no hidden prose |
| Image generator | 20 prompts: line-art, child-safe, simple objects, no text artifacts |
| Vision analyzer | 10 images: returns bounded trace strategy and rejects unsuitable input |
| SVG/vector model | 20 outputs: valid SVG path, bounded workspace, <= configured points |
| Recovery explainer | 20 error codes: correct user-facing reason and next action |

### Gate C: Geometry Safety

Generated artifacts must pass:

- workspace bounds;
- max point count;
- max feed rate;
- max runtime estimate;
- pen-up/pen-down encoding compatibility;
- preview artifact creation;
- simulator risk score below approval threshold, or explicit approval flow.

### Gate D: Route Behavior

Before first-tier promotion, record:

- backend id;
- provider;
- model id;
- command used for eval;
- fixture count;
- pass count;
- average latency;
- p95 latency when available;
- failure modes;
- admission decision;
- rollback rule.

Evidence should be linked from `docs/FREE_MODEL_ROUTING_STATUS.md` or a new
dated admission report. Route pool edits must not be mixed with unrelated
refactors.

## Switching Policy

Model switching is allowed when it improves reliability or safety, but it must
be explainable.

### User-Facing Model Aliases

Keep public aliases stable. Do not expose raw backend ids to product users.

| Alias | Meaning | Expected Backend Class |
|---|---|---|
| `lima-device` | default balanced device brain | deterministic first, admitted fast models second |
| `lima-device-fast` | speed over creativity | preset/deterministic/text-light |
| `lima-device-creative` | better drawing or text quality | image/text models with higher latency |
| `lima-device-safe` | conservative classroom/child mode | strict safety, low complexity, confirmation on risk |
| `lima-device-local` | local proxy/fallback when configured | local/fake/offline-capable backends only |

Aliases should map to route preferences, not directly to one provider forever.

### Automatic Switching Reasons

The router may switch backend when:

- current backend is dead, degraded, quarantined, cooled down, over budget, or
  retired;
- request requires a capability the current backend lacks;
- sticky backend is unsafe for the current task family;
- task complexity requires image/vision/vector capability;
- device profile requires lower point limits or smaller context;
- admission evidence ranks another backend higher for the role;
- operator has enabled a rollout/rollback flag.

The router must not switch because:

- a new provider exists but has no admission evidence;
- an LLM claims it can generate geometry without validator success;
- a web-reverse adapter works once without stability runs;
- a local Windows proxy is reachable from Windows but not from the VPS process;
- a paid fallback is cheaper to implement than fixing the correct free route,
  unless budget policy explicitly allows it.

## Prompt And Output Contracts

Planner models must return machine-readable JSON only. The device gateway must
not parse prose as authority.

Intent planner output:

```json
{
  "capability": "draw_generated",
  "params": {
    "prompt": "simple black line drawing of a cat, centered, no text",
    "style": "line_art",
    "complexity": "low"
  },
  "risk": "low",
  "needs_approval": false,
  "reason": "safe simple drawing request"
}
```

Text planner output:

```json
{
  "capability": "write_text",
  "params": {
    "text": "生日快乐",
    "layout": "single_line",
    "max_chars": 12
  },
  "risk": "low",
  "needs_approval": false
}
```

Image prompt output:

```json
{
  "image_prompt": "simple black line art of a smiling cat, white background, centered, no shading, no text",
  "negative_prompt": "photo, color, dense texture, background, letters, watermark",
  "size": "512x512"
}
```

Every model-produced object must be validated before it becomes a motion task.
Invalid JSON, extra prose, missing fields, or unsafe fields are route failures,
not partial successes.

## Device-Aware Routing Inputs

Route selection should eventually include device profile data from `hello` and
shadow state:

| Input | Use |
|---|---|
| `device_id` | sticky route, task ledger, per-device policy |
| `fw_rev` / `u1_fw_rev` | compatibility gates |
| `hw_rev` | workspace and GPIO risk assumptions |
| `profile_id` / `profile_rev` | feed, pen pressure, scale, max points |
| `workspace_mm` | path bounds and layout |
| `capabilities` | allowed task families |
| `limits.max_points` | vectorizer simplification target |
| `supports_crc` | U8/U1 transaction reliability mode |
| online/offline state | queue, retry, or reject decision |
| last failure code | recovery policy and backend downranking |

If profile data is missing, use conservative defaults and prefer writing/preset
routes over generated drawings.

## Safety And Policy Rules

Hard blocks:

- no motion without known `device_id`;
- no physical dispatch when device is unbound, transferred away, disposed,
  maintenance-locked, updating, or firmware-incompatible;
- no generated path outside workspace;
- no path exceeding point/feed/runtime limits;
- no hidden prompt injection from uploaded assets or user text;
- no provider secret in firmware, product repo, client app, or logs;
- no automatic retry of a hardware command after `E_U1_UNAVAILABLE`,
  `E_UNSUPPORTED_BOARD`, hard-limit alarm, or emergency stop.

Soft gates requiring approval or simplification:

- high simulator risk score;
- dense uploaded image;
- very long text;
- large fill areas;
- unknown material/profile;
- task estimated over the product latency/runtime budget.

The cloud may simplify scale, point count, or style before dispatch, but it must
record that simplification in the task artifact and user/operator explanation.

## Observability Requirements

Every AI-to-motion task should produce a traceable chain:

```text
request_id
  -> route_decision
  -> model/backend call evidence
  -> generated artifact
  -> vector/path artifact
  -> validation result
  -> simulation result
  -> policy decision
  -> dispatch event
  -> motion_event stream
  -> terminal result
```

Minimum fields for route evidence:

- `request_id`, `device_id`, `task_id`;
- task family and capability;
- selected backend and fallback chain;
- latency per stage;
- model output validity;
- safety decision;
- path point count, bounds, estimated runtime;
- final device phase;
- recovery action if failed.

## Verification Commands

Main LiMa checks for cloud/device integration:

```powershell
python -m pytest tests/test_device_gateway_routes.py -q
python -m pytest tests/test_device_protocol_validation.py -q
python -m pytest tests/test_routing_engine.py -q --tb=short
python scripts/run_pre_commit_check.py --full
```

Product repository checks before advancing the submodule pointer:

```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools/validate_schemas.py
python tools/check_gpio.py
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest tools.fake_u1.tests.test_app -v
python -m unittest tools.fake_device_server.tests.test_app -v
python -m unittest tools.fake_ai.tests.test_app -v
python -m unittest tools.fake_lima_u8.tests.test_app -v
python -m unittest tests.ci.test_fake_integration -v
```

Public endpoint smoke for a release candidate must include:

- `/device/v1/health`;
- fake U8 WebSocket session;
- one control command;
- one `write_text` task;
- one simple `draw_generated` task with preview artifact;
- one forced validation failure;
- one simulated device failure and recovery explanation.

## Roadmap

### Phase 1: Make Current Routes Explicit

- Document current deterministic parser and path pipeline behavior.
- Add route evidence for `write_text` and `draw_generated`.
- Keep `LIMA_DEVICE_LLM_PLANNER=0` by default.
- Prefer preset and deterministic drawing paths for demos.

### Phase 2: Admit Drawing Models By Role

- Build image-generation fixtures for line-art quality and vectorization
  success.
- Record evidence in a dated admission report.
- Add a dedicated drawing role route preference instead of reusing generic chat
  pools.
- Keep direct LLM-to-SVG as experimental until geometry fixtures pass.

### Phase 3: Device Profile-Aware Routing

- Include `workspace_mm`, `profile_rev`, `limits`, and firmware revisions in
  route decisions.
- Route low-capability devices to lower point counts and simpler styles.
- Add per-device sticky memory only after safety and profile compatibility are
  checked.

### Phase 4: Hardware-In-Loop Release Gate

- Run fake U8/U1 tests first.
- Run one physical device smoke per release candidate.
- Verify homing, stop, pause/resume, write, draw, disconnect recovery, and
  no-duplicate dispatch.
- Record the physical device evidence before claiming production readiness.

## Change Rules

- Update this document when adding or promoting a model used by
  drawing/writing routes.
- Update `docs/FREE_MODEL_ROUTING_STATUS.md` when evidence changes backend
  ranking or admission status.
- Update `docs/REQUEST_PIPELINE_AUTHORITY.md` only when route ownership or the
  production pipeline changes.
- Do not edit `router_v3.py` pools without focused tests and route evidence.
- Do not advance `esp32S_XYZ` submodule pointer without product-side tests or a
  clear reason why they could not run.
