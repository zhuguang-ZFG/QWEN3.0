# WeChat Channel Tools and Zero-Friction Guest Access

Date: 2026-05-25  
Status: Approved direction (owner + guest)  
Related: `docs/superpowers/plans/2026-05-25-wechat-chatbot-binding-plan.md`, REF-005

## Product decisions

1. **Scan QR / add friend → use immediately.** No `/bind <code>` required for guests.
2. **Guest and owner share one tool runtime** with different quotas and policies.
3. **Owner upgrade** stays explicit: env allowlist hash and/or one-time binding code.
4. All new tools and auto-bind are **default-off** in production until env enabled and smoke passes.

## Roles

| Role | How assigned | Capabilities |
|------|----------------|--------------|
| `guest` | Auto on first inbound message (when auto-bind on) | Chat, code help, draw demo, public tools (search/wiki/weather) |
| `owner` | `LIMA_CHANNEL_OWNER_HASHES` or successful `/bind <code>` from operator | Guest set + code-task, device, status, artifact, memory |

## Zero-friction bind flow

```text
User scans QR → adds WeChat bot → sends any message (e.g. 你好)
  → sidecar POST /channel/v1/wechat/message
  → ChannelService.ensure_guest_binding(sender_id)
  → active guest binding created (if none)
  → optional one-line welcome + normal command dispatch
```

`/bind <code>` becomes **optional**: operator code links a WeChat ID to a named `lima_user_id` (owner workflows), not a gate for guests.

`/unbind` sets `revoked`. Next message re-creates guest binding when auto-bind is enabled.

## Env switches

| Variable | Default | Meaning |
|----------|---------|---------|
| `WECHAT_BRIDGE_ENABLED` | `0` | Master switch for bridge |
| `LIMA_CHANNEL_AUTO_GUEST_BIND` | `1` | Auto guest binding on first message |
| `LIMA_CHANNEL_TOOLS` | `0` | Guest/owner tool commands (G1+) |
| `LIMA_CHANNEL_ID_SALT` | required | Hash channel user ids |

## Guest tool roadmap (G1–G5)

| Phase | Commands | Guest quota (per day) |
|-------|----------|------------------------|
| G0 | Auto-bind, `/help` `/menu` | — |
| G1 | `/百科` `/天气` | 15 / 10 |
| G2 | `/搜` `/新闻` `/翻译` `/汇率` `/时间` `/热搜` `/ip` | 8 / 5 / 10 / 10 / 30 / 5 / 5 |
| G3 | Channel multi-turn (6 turns), `/demo` script | — |
| G4 | `/读 <url>` (SSRF-safe; TinyFish 或简易 HTML 抽取) | 3 |
| G5 | Owner tools + digest (separate W-track) | 主人配额 × `LIMA_CHANNEL_OWNER_TOOL_MULT`（默认 3） |

**CQ-089 已实现：** `channel_gateway/channel_tools.py` + `public_apis.py` + `tool_usage.py`；`LIMA_CHANNEL_TOOLS=1` 开启。

## Security

- Tools call only through `search_gateway` URL safety (no SSRF).
- Guest replies never include VPS paths, API keys, backend names, or private memory.
- Rate limits stored per `channel_user_id_hash` in SQLite (future `channel_tool_usage` table).

## Implementation slices

1. **CQ-088 (this slice):** auto guest bind + help copy + tests.
2. **CQ-089:** `channel_tools` + 10+ 公开工具 + SQLite 日配额 ✅
3. **CQ-090:** 访客多轮会话、主人简报、VPS smoke

## Verification

```powershell
python -m pytest tests/test_channel_gateway_store.py tests/test_wechat_channel_smoke.py tests/test_channel_gateway_service.py -q
python -m pytest -q
```

VPS: `WECHAT_BRIDGE_ENABLED=1` + fake sidecar smoke; then real QR path when sidecar ready.
