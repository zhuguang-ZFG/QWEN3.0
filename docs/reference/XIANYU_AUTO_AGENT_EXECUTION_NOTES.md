# XianyuAutoAgent Execution Notes For LiMa

> Date: 2026-05-25
> Reference: https://github.com/shaxiu/XianyuAutoAgent
> Reviewed revision: `77b1e4c`
> License observed: GPL-3.0
> LiMa decision: concept/reference only. Do not vendor or copy source code.

## Purpose

This document converts the useful lessons from `shaxiu/XianyuAutoAgent` into
LiMa-native execution slices for LiMa Server, LiMa Code, and ESP32/Device
Gateway.

The reference project is valuable because it is a vertical always-on business
agent: it keeps a WebSocket session alive, stores conversation context, routes
messages to specialist agents, supports manual takeover, refreshes session
tokens, and runs as a Docker service. It is not valuable as a direct platform
integration dependency because it relies on cookies, private platform protocol
details, and GPL-3.0 source code.

LiMa should borrow the production shape, not the implementation.

## Executive Decision

| Area | Decision | Reason |
|---|---|---|
| Overall value | Medium-high | Useful as a working vertical-agent loop. |
| Runtime dependency | Rejected | GPL-3.0 plus platform-specific reverse/cookie flow. |
| Code reuse | Rejected | Do not copy source, prompts, protocol handlers, or request shapes. |
| Architecture reuse | Approved as concept | Channel connector, session store, router, experts, takeover, audit, health. |
| LiMa priority | P1 after P0.2 | Finish real Device Gateway path/text/SVG pipeline first, then generalize channel agents. |

## What Was Reviewed

| File | Relevant concept |
|---|---|
| `XianyuAgent.py` | Intent router, specialist agents, external prompt files, bargain-aware response policy. |
| `context_manager.py` | SQLite conversation history, per-chat counters, item metadata cache. |
| `main.py` | Long-lived WebSocket client, ACK handling, heartbeat loop, token refresh, manual takeover, message pipeline. |
| `XianyuApis.py` | Cookie/token refresh and platform-specific HTTP requests. Useful only as a cautionary boundary. |
| `Dockerfile`, `docker-compose.yml` | Minimal always-on service packaging with persistent data and prompts volumes. |
| `prompts/*_prompt_example.txt` | Role prompt separation. Useful only as a pattern; do not copy text. |

## Borrowed Concepts

### 1. Channel Connector Boundary

Reference behavior:

- A long-running process owns a platform connection.
- Incoming messages are normalized before business logic runs.
- Outgoing replies are sent through a narrow send function.
- Heartbeat, reconnect, and token refresh are connection concerns, not agent
  reasoning concerns.

LiMa adaptation:

```text
channel_connector/
  base.py              # ChannelMessage, ChannelReply, ConnectorHealth
  websocket_client.py  # generic heartbeat/reconnect helper
  telegram.py          # existing Telegram bridge can adapt later
  wechat.py            # future, gated
  web_chat.py          # LiMa private chat channel

agent_channels/
  pipeline.py          # normalize -> session -> route -> action -> audit
```

Do not put platform cookies, browser sessions, or private protocol logic in the
core router. Each connector must be default-off and separately approved.

### 2. Session Store And Conversation State

Reference behavior:

- SQLite stores messages by `chat_id`.
- A bounded history window is loaded for each response.
- Domain counters, such as bargain count, are stored separately and injected
  into context.

LiMa adaptation:

```text
session_memory/
  channel_sessions.py  # channel session rows and compact histories
  store.py             # existing typed memory remains durable source

agent_channels/
  session_state.py     # short-term per-channel state
```

Target fields:

| Field | Purpose |
|---|---|
| `channel` | `web`, `telegram`, `wechat`, `device`, `limacode`. |
| `conversation_id` | Stable channel conversation key. |
| `user_id_hash` | Redacted identity join key. |
| `task_id` | Optional LiMa task/work item link. |
| `device_id` | Optional Device Gateway link. |
| `manual_mode` | Human takeover state. |
| `last_intent` | Last routed intent. |
| `state_json` | Small typed state, not raw secrets. |
| `updated_at` | Recovery and timeout logic. |

For HA, use Postgres or Redis-backed state only after the channel pipeline
proves useful locally. Do not expand storage before P0 device execution is
stable.

### 3. Intent Router Plus Specialist Agents

Reference behavior:

- Rules catch obvious intents first.
- LLM classification handles ambiguous messages.
- Specialist agents handle price, technical, default, and classify paths.
- Prompt files are externalized.

LiMa adaptation:

```text
agent_channels/
  intent_router.py
  experts/
    code_work.py
    device_motion.py
    ops_debug.py
    memory_recall.py
    default_reply.py
  prompt_profiles.py
```

Initial LiMa intents:

| Intent | Owner | First useful action |
|---|---|---|
| `code_plan` | LiMa Code | Produce a reviewable implementation plan. |
| `code_fix` | LiMa Code | Create or claim a bounded fix task. |
| `device_motion` | Device Gateway | Convert safe command into previewable path task. |
| `ops_debug` | Server | Return correlated health/task/device status. |
| `memory_query` | Session memory | Recall cited project facts. |
| `human_takeover` | Operator | Pause automation for a conversation/task/device. |
| `no_reply` | Channel pipeline | ACK without agent reply. |
| `default_chat` | Router | Normal private assistant response. |

Router rules:

- Deterministic rules first for safety-critical hardware and ops phrases.
- Model-backed classification only after redaction and prompt-profile versioning.
- Every model-routed intent must include a reason and confidence.
- Unsafe or ambiguous hardware commands must become `rejected_command`, not
  best-effort execution.

### 4. Manual Takeover

Reference behavior:

- Per-chat manual mode can be toggled.
- Manual mode has a timeout.
- Bot records human replies but does not auto-reply while takeover is active.

LiMa adaptation:

Manual takeover must exist at three levels:

| Scope | Meaning |
|---|---|
| `conversation` | Stop automatic replies in one channel thread. |
| `task` | Stop a LiMa Code or Device Gateway task. |
| `device` | Stop dispatching motion tasks to a device. |

Required state:

```text
takeover_id
scope
scope_id
owner
reason
expires_at
created_at
released_at
audit_event_id
```

Exit criteria:

- A human can pause one device or one conversation without shutting down LiMa.
- The operator view shows who paused it, why, and when it expires.
- Automation resumes only after timeout or explicit release.

### 5. WebSocket Health And Recovery

Reference behavior:

- Heartbeat loop detects stale connection.
- Token refresh can trigger connection restart.
- Reconnect loop keeps the process alive.
- ACK is sent for received frames.

LiMa adaptation:

Device Gateway already has WebSocket handling and Redis HA. The next useful
upgrade is a common health vocabulary for all long-lived channels:

| Health field | Meaning |
|---|---|
| `connected` | Whether the connector currently has a live session. |
| `last_seen_at` | Last inbound frame or heartbeat ack. |
| `last_send_at` | Last outbound frame. |
| `reconnect_count` | Number of reconnects since start. |
| `last_error_code` | Stable failure class. |
| `listener_alive` | Whether background listener task is still running. |
| `owner_process_id` | Which process owns the active session. |

Tie this into the existing Redis session-owner strategy so HTTP tasks can wake
the process that owns a WebSocket session.

### 6. Prompt Profiles

Reference behavior:

- Prompts are file-backed and reloadable.
- Each expert has a separate prompt file.

LiMa adaptation:

Create prompt profiles, not free-form prompt files:

```text
prompt_profiles/
  code_plan.v1.md
  code_review.v1.md
  device_motion.v1.md
  ops_debug.v1.md
  memory_query.v1.md
```

Each profile needs metadata:

```text
profile_id
version
owner
allowed_tools
risk_class
eval_fixture
rollback_profile_id
```

Prompts must be evaluated against fixtures before becoming default. Hot reload
is useful only after audit, versioning, and rollback exist.

### 7. Observability And Audit

Reference behavior:

- Loguru prints useful runtime events.
- Logs include message handling, mode switches, and connection events.

LiMa adaptation:

Use LiMa's structured observability rather than plain logs only.

Minimum events:

| Event | Required ids |
|---|---|
| `channel.message.received` | `channel`, `conversation_id`, `request_id`. |
| `channel.intent.routed` | `intent`, `confidence`, `profile_id`, `request_id`. |
| `channel.takeover.changed` | `scope`, `scope_id`, `owner`, `request_id`. |
| `channel.reply.sent` | `channel`, `conversation_id`, `task_id`, `request_id`. |
| `channel.connector.reconnected` | `channel`, `reconnect_count`, `last_error_code`. |
| `device.motion.dispatched` | `device_id`, `task_id`, `motion_task_id`. |
| `limacode.task.submitted` | `task_id`, `artifact_bundle_id`, `review_status`. |

All events must redact raw user ids, tokens, cookies, API keys, and raw private
messages unless an explicit debug export is approved.

## What Not To Borrow

| Reference behavior | LiMa decision |
|---|---|
| Cookie-string platform login | Do not add to core. Connector-specific and default-off only. |
| Private platform WebSocket protocol | Do not copy. Use only public/approved APIs or user-approved connectors. |
| Updating `.env` with refreshed cookies | Reject. Secrets must stay in controlled env stores. |
| Interactive credential prompts in service startup | Reject for production. Services must fail clearly. |
| SQLite as HA state | Use only for local/dev. HA requires Redis/Postgres design. |
| Global `bot` instance shared by handlers | Avoid. Use dependency-injected pipeline state. |
| Prompt text copying | Reject. GPL and product mismatch. |
| Simulated human typing | Low priority. It does not improve LiMa productivity. |

## Execution Plan

### Phase A - Documentation And Ledger

Status: this document.

- Record reference value and boundaries.
- Add ledger entry as `concept`.
- Add LiMa follow-up phases and gates.

Exit:

- Future sessions can find the reference and know not to copy code.

### Phase B - Channel Agent Interface

Priority: P1, after P0.2 real path/text/SVG pipeline.

Files:

- Create: `agent_channels/types.py`
- Create: `agent_channels/pipeline.py`
- Create: `agent_channels/intent_router.py`
- Create: `agent_channels/takeover.py`
- Test: `tests/test_agent_channels.py`

Tasks:

- Define `ChannelMessage`, `ChannelReply`, `ChannelIntent`, and
  `ChannelPipelineResult`.
- Add deterministic router rules for `code_plan`, `code_fix`, `device_motion`,
  `ops_debug`, `memory_query`, `human_takeover`, and `default_chat`.
- Add a fake connector fixture that simulates inbound messages and outbound
  replies.
- Add audit events without sending real network messages.

Exit:

- A fake channel message can route to a typed intent, create a task or reply,
  and record an audit event with redacted ids.

### Phase C - Session State And Manual Takeover

Priority: P1.

Files:

- Create: `agent_channels/session_state.py`
- Create: `agent_channels/store.py`
- Modify: `session_memory/store.py` only if a typed memory hook is needed.
- Test: `tests/test_agent_channel_sessions.py`

Tasks:

- Store bounded per-conversation state.
- Add manual takeover state with expiration.
- Add conversation/task/device takeover scopes.
- Add API helpers for pause, release, and status.

Exit:

- Automation can be paused for one conversation, one task, or one device.
- Expired takeover is released deterministically.
- Audit records show pause/release reason and owner.

### Phase D - Ops Metrics Correlation

Priority: P1.

Files:

- Modify or create: `routes/ops_metrics.py`
- Modify: `observability/events.py`
- Modify: `observability/metrics.py`
- Test: `tests/test_ops_metrics.py`

Tasks:

- Join channel, request, worker, task, and device ids into one redacted
  operator snapshot.
- Expose authenticated read-only status.
- Include connector health, listener status, and recent failure classes.

Exit:

- One command or endpoint answers: which request, which route, which worker,
  which task, which device, and where it failed.

### Phase E - Prompt Profile Registry

Priority: P1/P2.

Files:

- Create: `prompt_profiles/`
- Create: `prompt_profiles/registry.py`
- Test: `tests/test_prompt_profiles.py`

Tasks:

- Add prompt metadata and versioning.
- Add profile ownership and rollback profile.
- Link profile to eval fixtures.
- Record prompt profile id in route/task/channel events.

Exit:

- A prompt change can be evaluated, rolled back, and traced to outcomes.

### Phase F - Optional Messaging Connectors

Priority: P2, gated.

Candidates:

- Telegram: existing LiMa surface first.
- WeChat: only after explicit account, platform-term, credential, and
  anti-abuse review.
- Other social channels: default-off.

Required gates:

- Owner.
- Credential boundary.
- Platform-term review.
- Rate-limit policy.
- Outbound-message approval mode.
- Audit and redaction.
- Stop switch.

Exit:

- A connector can run in fake mode and manual-approval mode before any
  autonomous outbound messages are allowed.

## Acceptance Criteria

The reference is considered successfully absorbed only when LiMa has all of:

- A LiMa-owned channel pipeline with fake connector tests.
- A deterministic intent router with model classification behind a gate.
- Bounded session state with manual takeover.
- Structured audit events for route, reply, takeover, and connector health.
- Ops metrics that correlate channel messages to LiMa Code or Device Gateway
  tasks.
- Prompt profile ids tied to eval evidence.
- No copied GPL source code, no copied prompts, and no default cookie-based
  connector.

## Verification Commands

For the documentation-only slice:

```powershell
git diff --check -- docs/reference/XIANYU_AUTO_AGENT_EXECUTION_NOTES.md docs/REFERENCE_IMPLEMENTATION_LEDGER.md docs/DOCUMENTATION_STATUS.md docs/LIMA_MEMORY.md progress.md findings.md STATUS.md
rg -n "XianyuAutoAgent|shaxiu|Channel Connector|manual takeover" docs/reference/XIANYU_AUTO_AGENT_EXECUTION_NOTES.md docs/REFERENCE_IMPLEMENTATION_LEDGER.md docs/DOCUMENTATION_STATUS.md docs/LIMA_MEMORY.md progress.md findings.md STATUS.md
```

For the first implementation slice:

```powershell
python -m py_compile agent_channels/types.py agent_channels/pipeline.py agent_channels/intent_router.py agent_channels/takeover.py
python -m pytest tests/test_agent_channels.py -q --ignore=active_model
git diff --check -- agent_channels tests/test_agent_channels.py
```

## Risk Register

| Risk | Mitigation |
|---|---|
| Copying GPL source by accident | Keep this as architecture notes only; no vendoring. |
| Social connector abuse | Default-off, owner approval, rate limits, audit, stop switch. |
| Credential leakage | Never store cookies/tokens in docs, logs, task payloads, or memory. |
| Agent replies without human control | Manual takeover and outbound approval mode before autonomous connectors. |
| More channels before core productivity | P0.2 Device Gateway execution remains ahead of messaging expansion. |
| Prompt drift | Prompt profiles need version, eval, and rollback. |

## Next Recommended Slice

Do not start with WeChat or Xianyu-specific integration. Start with a fake
channel connector and reuse it to drive two productive LiMa flows:

1. `device_motion`: "write LiMa" -> preview -> fake U8 task -> motion events.
2. `code_fix`: "fix failing test" -> LiMa Code artifact bundle -> review
   status.

Once these fake-channel flows produce real artifacts and correlated ops
metrics, adding Telegram or WeChat becomes an adapter problem instead of a new
agent architecture problem.
