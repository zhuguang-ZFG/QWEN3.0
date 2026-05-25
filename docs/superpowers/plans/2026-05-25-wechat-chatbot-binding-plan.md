# WeChat Chatbot Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight WeChat guest-experience robot for LiMa with QR/code-based user binding, safe public chat/demo commands, and a later owner-only path for LiMa Code, Device Gateway, status, and artifact lookup.

**Architecture:** WeChat is only the channel. LiMa Server remains the control plane for identity binding, guest/owner roles, sessions, routing, demo tasks, memory, audit, and later owner-only device/task actions. A separate WeChat sidecar owns login/session custody and forwards normalized messages into LiMa through a small Channel Gateway API. Start with a fake WeChat connector, then attach the real WeChat bridge behind allowlists, rate limits, dedupe, and a kill switch.

**Tech Stack:** Python/FastAPI in LiMa Server, SQLite first for binding/session/audit state, optional Redis later for HA, existing `routing_engine` and Device Gateway path-preview helpers for guest demos, plus a sidecar process for real WeChat integration. Existing `agent_tasks`, real `device_gateway`, and LiMa Code artifact bundles are reserved for owner-only v2 commands.

---

## Product Decision

This plan explicitly does not use Enterprise WeChat. It targets personal WeChat-style chat interaction through a separate bridge/sidecar.

The first product surface is a guest experience bot, not an operator control bot. It should be safe to share with other people for lightweight LiMa demos. No approval commands are part of v1, and v1 does not expose private project control.

V1 guest commands:

- plain text or `/chat <message>` -> public/demo LiMa Chat persona;
- `/code <question>` -> safe code explanation or suggestion, not a real task;
- `/draw <prompt>` -> generate a preview/demo path, not a real device job;
- `/demo` -> explain LiMa capabilities with a short guided demo;
- `/about` -> explain LiMa in visitor-friendly language;
- `/reset` -> clear the visitor's lightweight session;
- `/bind <code>`, `/unbind`, `/pause`, `/resume`, `/help`.

V2 owner-only commands, not enabled for guests:

- `/code-task <goal>` -> create a LiMa Code/Server task;
- `/device <command>` -> create a Device Gateway task;
- `/status` -> return private operator status;
- `/artifact <task_id>` -> return LiMa Code artifact bundle summary;
- `/memory recent` or `/memory search <query>` -> query private LiMa memory.

## V1 Guest Experience Amendment

When this document mentions task creation, real Device Gateway dispatch,
artifact lookup, private status, or private memory in later sections, treat
those capabilities as V2 owner-only follow-up unless the step explicitly says
"guest". V1 is intentionally lightweight so the bot can be shared with other
people for safe LiMa demos.

V1 must implement:

- visitor binding as `guest`;
- private-chat text and `/chat`;
- `/code` as explanation/suggestion only;
- `/draw` as preview/demo only, never real hardware dispatch;
- `/demo`, `/about`, `/help`, `/reset`;
- `/pause`, `/resume`, `/unbind`;
- owner-only rejection for `/status`, `/device`, `/artifact`, `/memory`, and
  `/code-task`.

V1 must not implement for guests:

- Server task creation;
- LiMa Code worker execution;
- repository reads;
- artifact patch/detail reads;
- VPS logs/status/metrics;
- private memory queries;
- real Device Gateway queueing;
- deployment, restart, shell, or push actions.

## Non-Negotiable Boundaries

- Do not put WeChat login cookies, QR tokens, contact lists, or raw sidecar secrets into model context.
- Do not commit runtime WeChat state, cookies, QR images, local sidecar DBs, or chat exports.
- Only bound users can talk to LiMa.
- New bindings default to `guest`, not `owner`.
- Guests cannot access VPS state, logs, private memory, real LiMa Code tasks, real Device Gateway tasks, artifact internals, local repository paths, deployment controls, or hardware controls.
- Owner capabilities require explicit server-side allowlist, e.g. `LIMA_CHANNEL_OWNER_HASHES`, and are out of v1.
- Group chat is disabled until private chat is reliable. When enabled later, require group allowlist plus mention/prefix.
- Outbound proactive messages are disabled in v1 except direct replies to the current guest conversation.
- Every inbound message gets deduped by channel message id.
- Every command is rate-limited per user.
- Guest demo commands never execute shell, deploy, read private repos, create Server tasks, or move real hardware.
- Hardware and code execution continue to follow existing LiMa safety gates when owner-only v2 commands are enabled.
- Global kill switch: `WECHAT_BRIDGE_ENABLED=0` makes every WeChat endpoint return disabled/ack without processing.

## Existing References To Reuse

- `docs/reference/XIANYU_AUTO_AGENT_EXECUTION_NOTES.md`:
  use the `ChannelConnector -> SessionStore -> IntentRouter -> ExpertAgent -> HumanTakeover -> AuditLog -> TaskQueue` shape, but no Xianyu code or private protocol details.
- `docs/reference/MCP_CONNECTOR_CATALOG.md`:
  messaging bridges are default-off concept references and need allowlists, credential custody, consent, outbound approval/audit, timeout, and failure modes.
- `wechatapp/`:
  useful for future mini-program workbench and WeChat login/user concepts, not the first chat robot bridge.
- `routes/telegram.py` and `routes/telegram_commands.py`:
  useful as command-surface reference, but this plan avoids Telegram approval flow.

## File Map

### New LiMa Server Package

- `channel_gateway/__init__.py`
  Package exports for channel gateway models and service helpers.
- `channel_gateway/models.py`
  Dataclasses or Pydantic models for normalized inbound/outbound messages, binding state, command result, and audit events.
- `channel_gateway/store.py`
  SQLite-backed binding/session/audit store. One file for v1; split later only if it grows.
- `channel_gateway/commands.py`
  Command parser and dispatcher for guest commands (`/bind`, `/chat`, `/code`, `/draw`, `/demo`, `/about`, `/reset`, `/pause`, `/resume`, `/unbind`, `/help`) plus owner-only rejection for `/code-task`, `/device`, `/status`, `/artifact`, and `/memory`.
- `channel_gateway/service.py`
  Orchestrates dedupe, auth/binding checks, command dispatch, chat routing, and outbound response building.
- `routes/channel_gateway.py`
  Private sidecar API: start binding, receive WeChat messages, query binding state, and report bridge health.

### Optional New Scripts

- `scripts/smoke_wechat_channel_gateway.py`
  Local smoke that uses fake sidecar messages against FastAPI/TestClient or live localhost.
- `scripts/wechat_bridge_fake.py`
  CLI helper for manual fake-message testing while real sidecar is not ready.

### Tests

- `tests/test_channel_gateway_models.py`
- `tests/test_channel_gateway_store.py`
- `tests/test_channel_gateway_commands.py`
- `tests/test_channel_gateway_routes.py`
- `tests/test_wechat_channel_smoke.py`

### Docs

- `docs/WECHAT_CHATBOT.md`
  Operator runbook, env vars, binding flow, command list, safety boundaries, and smoke steps.
- Update `STATUS.md`, `progress.md`, `findings.md`, and `docs/LIMA_MEMORY.md` after each completed slice.

## Data Model

### `channel_bindings`

| Field | Type | Notes |
|---|---|---|
| `binding_id` | text primary key | `bind_...` |
| `channel` | text | `wechat` in v1 |
| `channel_user_id_hash` | text | SHA-256 of sidecar user id plus server-side salt |
| `display_name` | text | Redacted or operator-friendly name |
| `lima_user_id` | text | Local LiMa user/session owner id |
| `role` | text | `guest` by default; `owner` only by allowlist |
| `status` | text | `pending`, `active`, `paused`, `revoked` |
| `created_at` | integer | Unix seconds |
| `updated_at` | integer | Unix seconds |

### `channel_binding_codes`

| Field | Type | Notes |
|---|---|---|
| `code_hash` | text primary key | Store hash, not raw code |
| `lima_user_id` | text | Owner that requested binding |
| `expires_at` | integer | 5-10 minutes |
| `used_at` | integer nullable | Set once |
| `created_at` | integer | Unix seconds |

### `channel_messages`

| Field | Type | Notes |
|---|---|---|
| `message_id` | text primary key | Sidecar message id |
| `channel` | text | `wechat` |
| `channel_user_id_hash` | text | Hash only |
| `conversation_id_hash` | text | Hash only |
| `direction` | text | `inbound` or `outbound` |
| `intent` | text | `guest_chat`, `guest_code_help`, `guest_draw_demo`, `owner_code_task`, etc. |
| `task_id` | text nullable | Server task link |
| `device_id` | text nullable | Device link |
| `summary` | text | Redacted short summary |
| `created_at` | integer | Unix seconds |

## Public/Internal API Design

All endpoints live behind private API auth or a dedicated sidecar token. The sidecar token must be separate from `LIMA_API_KEY`.

### `POST /channel/v1/bind/start`

Purpose: create a short-lived binding code for the current LiMa operator/user.

Request:

```json
{
  "channel": "wechat",
  "lima_user_id": "owner"
}
```

Response:

```json
{
  "binding_code": "123456",
  "expires_at": 1770000000,
  "instructions": "Send /bind 123456 to the WeChat robot."
}
```

For the first implementation, the "QR" can encode the binding instructions or a local web binding URL. Real WeChat sidecar QR login is separate from user binding.

### `POST /channel/v1/wechat/message`

Purpose: sidecar posts normalized inbound WeChat messages.

Request:

```json
{
  "message_id": "wechat-msg-1",
  "sender_id": "raw-sidecar-user-id",
  "conversation_id": "raw-sidecar-conversation-id",
  "conversation_type": "private",
  "text": "/chat hello",
  "timestamp": 1770000000
}
```

Response:

```json
{
  "ok": true,
  "reply": {
    "text": "hello from LiMa"
  }
}
```

### `GET /channel/v1/wechat/health`

Purpose: sidecar and operator health check.

Response:

```json
{
  "enabled": true,
  "bound_users": 1,
  "recent_messages": 5
}
```

## Command Behavior

### `/bind <code>`

- Allowed for unbound users.
- Validates code hash and expiry.
- Creates active binding for `sender_id`.
- Replies with short success message and `/help`.

### Plain Text And `/chat <message>`

- Requires active binding.
- Routes through a public/demo LiMa chat persona.
- Must not include private project memory, private artifact content, VPS status, local paths, or secrets.
- Uses channel-scoped compact history later; first slice can be stateless plus audit.

### `/code <question>`

- Requires active binding.
- Guest role: answers as code help/explanation only. It does not create Server tasks, call LiMa Code worker, or read local repositories.
- Owner role in v2: use `/code-task <goal>` for bounded Server task creation.

### `/draw <prompt>`

- Requires active binding.
- Guest role: generates a safe demo preview only, such as text/path preview metadata. It must not send to a real device.
- Reuse the Device Gateway path pipeline where possible, but stop before queueing or dispatching.

### `/demo`

- Requires active binding.
- Returns a short guided list of what guests can try: chat, code help, draw demo, about, reset.
- Does not expose internal health or ops metrics.

### `/about`

- Requires active binding.
- Explains LiMa as a private coding/hardware assistant in visitor-safe language.

### Owner-Only V2 Commands

- `/code-task <goal>` creates a bounded Server task.
- `/device <command>` creates a Device Gateway task.
- `/status` reads private ops metrics.
- `/artifact <task_id>` reads `.lima/artifacts/<task_id>/`.
- `/memory recent` or `/memory search <query>` reads private memory.
- These commands must return "owner only" for guest users.

### `/pause`, `/resume`, `/unbind`

- `/pause`: binding status becomes `paused`; only `/resume`, `/unbind`, `/help` work.
- `/resume`: returns to `active`.
- `/unbind`: binding status becomes `revoked`.

## Implementation Tasks

### Task 1: Channel Models And Store

**Files:**
- Create: `channel_gateway/models.py`
- Create: `channel_gateway/store.py`
- Create: `channel_gateway/__init__.py`
- Test: `tests/test_channel_gateway_store.py`

- [ ] Write tests for binding code creation, expiry, one-time use, default guest role, owner allowlist promotion, active binding lookup, paused/revoked behavior, message dedupe, and audit summary storage.
- [ ] Implement SQLite tables with repo-local default path under `data/channel_gateway.db`.
- [ ] Add env override `LIMA_CHANNEL_DB_PATH`.
- [ ] Hash raw WeChat ids using `LIMA_CHANNEL_ID_SALT`; fail closed if salt is missing in production mode, use deterministic test salt in tests.
- [ ] Run:

```powershell
python -m pytest tests/test_channel_gateway_store.py -q
```

Expected: all tests pass.

### Task 2: Command Parser

**Files:**
- Create: `channel_gateway/commands.py`
- Test: `tests/test_channel_gateway_commands.py`

- [ ] Write tests for `/bind`, `/chat`, plain text, `/code`, `/draw`, `/demo`, `/about`, `/reset`, owner-only command rejection for guests, `/pause`, `/resume`, `/unbind`, `/help`, unknown commands, empty commands, and overlong text.
- [ ] Implement a small parser returning `{intent, args, raw_text}`.
- [ ] Enforce max text length, e.g. `LIMA_CHANNEL_MAX_TEXT=4000`.
- [ ] Run:

```powershell
python -m pytest tests/test_channel_gateway_commands.py -q
```

Expected: all tests pass.

### Task 3: Channel Service

**Files:**
- Create: `channel_gateway/service.py`
- Test: `tests/test_channel_gateway_service.py`

- [ ] Write tests for unbound user behavior, successful `/bind`, duplicate message no-op, paused user, guest plain chat dispatch, guest code help, guest draw demo, guest `/demo`, guest `/about`, guest `/reset`, and guest rejection for owner-only commands.
- [ ] Implement service with dependency injection for chat/demo handlers so tests do not call network or real models.
- [ ] Redact raw ids and secrets before audit writes.
- [ ] Run:

```powershell
python -m pytest tests/test_channel_gateway_service.py -q
```

Expected: all tests pass.

### Task 4: FastAPI Routes

**Files:**
- Create: `routes/channel_gateway.py`
- Modify: `server.py` or route-registration module used by the current app
- Test: `tests/test_channel_gateway_routes.py`

- [ ] Write tests for `/channel/v1/bind/start`, `/channel/v1/wechat/message`, auth failure, disabled kill switch, duplicate message, and health.
- [ ] Add sidecar auth using `LIMA_WECHAT_SIDECAR_TOKEN`.
- [ ] Add global enable flag `WECHAT_BRIDGE_ENABLED`.
- [ ] Register routes in the main app.
- [ ] Run:

```powershell
python -m pytest tests/test_channel_gateway_routes.py -q
```

Expected: all tests pass.

### Task 5: Guest-Safe LiMa Integrations

**Files:**
- Modify: `channel_gateway/service.py`
- Possibly create: `channel_gateway/integrations.py`
- Test: `tests/test_channel_gateway_integrations.py`

- [ ] Chat integration: call `routing_engine.route()` with guest persona and without private memory injection.
- [ ] Code help integration: answer coding questions without creating tasks or reading local repositories.
- [ ] Draw demo integration: use the path pipeline to produce preview-safe metadata without queueing or dispatching to Device Gateway.
- [ ] Demo/about integration: return static, visitor-safe capability summaries.
- [ ] Reset integration: clear only the guest's lightweight channel session.
- [ ] Owner-only command integration: return a clear "owner only" response for guest role.
- [ ] Run:

```powershell
python -m pytest tests/test_channel_gateway_integrations.py tests/test_device_gateway_path_validator.py -q --ignore=active_model
```

Expected: all tests pass.

### Task 6: Fake WeChat Sidecar Smoke

**Files:**
- Create: `scripts/wechat_bridge_fake.py`
- Create: `scripts/smoke_wechat_channel_gateway.py`
- Test: `tests/test_wechat_channel_smoke.py`

- [ ] Implement a fake sidecar that posts normalized messages to `/channel/v1/wechat/message`.
- [ ] Smoke sequence:
  - start binding code;
  - send `/bind <code>`;
  - send plain chat;
  - send `/demo`;
  - send `/code explain a debounce function`;
  - send `/draw write LiMa`;
  - send `/status` and verify owner-only response;
  - send `/device write LiMa` and verify owner-only response;
  - send duplicate message id and verify no duplicate side effects.
- [ ] Run:

```powershell
python scripts/smoke_wechat_channel_gateway.py --base-url http://127.0.0.1:8080
```

Expected: smoke prints each step and exits 0.

### Task 7: Real WeChat Sidecar Adapter

**Files:**
- Create under a separate folder, for example: `wechat_bridge/`
- Do not vendor reference code unless license and copying boundaries are explicitly approved.
- Test: sidecar unit tests plus fake integration tests.

- [ ] Pick the actual sidecar implementation after local evaluation of the reference project.
- [ ] Sidecar owns WeChat login QR/session and raw message polling/listening.
- [ ] Sidecar posts normalized messages only; raw cookies and contact exports never leave sidecar state.
- [ ] Sidecar supports:
  - private chat inbound text;
  - outbound reply;
  - message id;
  - sender id;
  - conversation id;
  - reconnect/backoff;
  - local health endpoint;
  - stop switch.
- [ ] Verify with one bound guest account and no group chat.

Expected: guest can bind and have a normal private chat/demo experience with LiMa in WeChat.

### Task 8: VPS Deployment And Evidence

**Files:**
- Update: `docs/WECHAT_CHATBOT.md`
- Update: `STATUS.md`, `progress.md`, `findings.md`, `docs/LIMA_MEMORY.md`

- [ ] Backup VPS runtime before deployment.
- [ ] Deploy only LiMa Server changes needed for Channel Gateway.
- [ ] If sidecar runs on VPS, create a dedicated systemd service with environment file and no secrets in repo.
- [ ] If sidecar runs on Windows/local machine, document FRP or local tunnel route separately.
- [ ] Verify:
  - `/channel/v1/wechat/health`;
  - fake sidecar smoke;
  - real private WeChat `/bind`;
  - real private WeChat plain chat;
  - `/demo`;
  - `/about`;
  - `/code explain a debounce function`;
  - `/draw write LiMa`;
  - owner-only rejection for `/status`, `/device`, `/artifact`, `/memory`, and `/code-task`;
  - duplicate-message no-op;
  - `/pause` and `/resume`.
- [ ] Record backup path, commit hash, smoke outputs, and residual risks.

## Testing Matrix

| Layer | Command | Expected |
|---|---|---|
| Store | `python -m pytest tests/test_channel_gateway_store.py -q` | Pass |
| Parser | `python -m pytest tests/test_channel_gateway_commands.py -q` | Pass |
| Service | `python -m pytest tests/test_channel_gateway_service.py -q` | Pass |
| Routes | `python -m pytest tests/test_channel_gateway_routes.py -q` | Pass |
| Integrations | `python -m pytest tests/test_channel_gateway_integrations.py tests/test_device_gateway_path_validator.py -q --ignore=active_model` | Pass |
| Smoke | `python scripts/smoke_wechat_channel_gateway.py --base-url http://127.0.0.1:8080` | Exit 0 |
| Full Server | `python -m pytest -q --ignore=active_model` | No regression |

For V1 guest implementation, the integration smoke must verify guest-safe
behavior first:

- `/bind <code>` succeeds and assigns `guest`;
- plain text and `/chat` reply;
- `/code explain a Python debounce function` replies without creating a task;
- `/draw write LiMa` returns demo/preview metadata without Device Gateway
  queueing;
- `/demo`, `/about`, and `/reset` reply;
- `/status`, `/device`, `/artifact`, `/memory`, and `/code-task` return
  owner-only responses for guests;
- duplicate message id does not produce duplicate side effects.

## Security Review Checklist

- [ ] No WeChat cookies, tokens, QR state, or raw session files committed.
- [ ] `LIMA_WECHAT_SIDECAR_TOKEN` required for sidecar API.
- [ ] `WECHAT_BRIDGE_ENABLED=0` disables processing.
- [ ] Only active bound users can chat.
- [ ] New bindings default to `guest`.
- [ ] Guests cannot create Server tasks, read artifacts, query private memory, view ops metrics, deploy, restart, run shell, push, or control real devices.
- [ ] Owner-only commands are explicitly rejected for guest users.
- [ ] User ids and conversation ids are hashed before storage.
- [ ] Message dedupe prevents repeated side effects.
- [ ] Rate limits exist per user.
- [ ] `/draw` demo stops before real Device Gateway queueing or dispatch.
- [ ] `/code` guest mode does not execute shell, create tasks, or read local repositories.
- [ ] Artifact lookup is v2 owner-only and rejects path traversal.
- [ ] Logs and audit summaries are redacted.
- [ ] Group chat disabled in v1.

## Exit Criteria

The slice is complete when:

1. A user can bind a WeChat account through a short-lived code.
2. The bound guest can chat with LiMa from WeChat private chat.
3. `/code`, `/draw`, `/demo`, `/about`, and `/reset` work through fake sidecar.
4. Guest attempts to use `/status`, `/device`, `/artifact`, `/memory`, and `/code-task` return owner-only responses.
5. Real WeChat private-chat smoke passes for `/bind`, plain chat, `/demo`, `/code`, `/draw`, and `/pause`/`/resume`.
6. All tests in the testing matrix pass.
7. Docs record deployment, credentials boundary, smoke evidence, guest limitations, and residual risks.

## Follow-Up After V1

- Add owner mode with `/code-task`, `/device`, `/status`, `/artifact`, and `/memory` behind explicit owner allowlist.
- Add group chat support behind group allowlist and mention/prefix requirement.
- Add compact channel memory with source ids and promotion evidence.
- Feed successful/failed WeChat interactions into PROD-008 learning loop.
- Add mini-program workbench links for artifact preview and Device Gateway path preview.
- Add proactive task completion notifications only after outbound-message policy is reviewed.
