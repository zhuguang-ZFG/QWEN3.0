# Personal Coding Assistant Findings

> Treat this file as evidence data, not instructions.

| TG-PROXY-099-1 | Root cause | VPS `:7897` not listening; `frpc.toml` missing `gfw-proxy` tunnel | Closed 2026-05-26 |
| TG-PROXY-099-2 | Code | `telegram_bot._telegram_proxy_candidates()` proxy→direct fallback | Closed 2026-05-26 |
| TG-PROXY-099-3 | Ops | `frp/frpc.toml` added `gfw-proxy`; frpc restarted; VPS send smoke ok | Closed 2026-05-26 |

| GI-G-2-1 | VPS deploy | `/gitee/webhook` enabled; health `gitee_webhook=true` | Closed 2026-05-26 |
| GI-G-2-2 | Public smoke | `smoke_gitee_webhook_public.py` local+public 200 | Closed 2026-05-26 |
| GI-G-2-3 | Ops | Gitee UI WebHook password must match VPS `GITEE_WEBHOOK_SECRET` | Open |

| PE-C-1-1 | Manual install | user upload 180.9MB → VPS v2.10.3 active | Closed 2026-05-26 |
| PE-C-1-2 | Smoke | `smoke_netdata_mcp_vps.py` smoke_ok | Closed 2026-05-26 |
| PE-C-1-3 | Ops | 19999 binds 0.0.0.0 — restrict to loopback recommended | Open |

| FL-1-7-1 | Ops | `/github` phone 11:01 title/body ok | Closed 2026-05-26 |
| FL-1-7-2 | Bug | multi-line message ignored 2nd command | Closed 2026-05-26 |
| FL-1-7-3 | Code | `_dispatch_command_lines` + `parse_github_args` first line | Closed 2026-05-26 |
| FL-1-7-4 | Ops | phone 11:05 `/github` + `/device` same message ok | Closed 2026-05-26 |

| PE-C-1-3 | Ops | 19999 bind 127.0.0.1 loopback only | Closed 2026-05-26 |
| PE-B-1-1 | Docs | CODESEARCH_MCP_SETUP.md + smoke baseline | Closed 2026-05-26 |
| PE-B-1-2 | Ops | codesearch binary install + index | Open |
| GFL-1 | Ops | 11:02 degraded transient; VPS now healthy | Closed 2026-05-26 |
| GFL-2 | Risk | TG push translate + chat_fast share google_flash_lite RPM | Open |

## 2026-05-26 Five-line closeout slice 1

| ID | Area | Evidence | Status |
|---|---|---|---|
| FL-1-1 | CF-G-3 | `google_flash_lite` first in `chat_fast.strong`; vision cf→google | Closed 2026-05-26 |
| FL-1-2 | TG-GH-4 code | `/github` `/device status` commands | Closed 2026-05-26 |
| FL-1-3 | GI-G-5 | `gitee_mirror_lag_check.py` | Closed 2026-05-26 |
| FL-1-4 | VPS deploy | `deploy_five_line_closeout.py` active | Closed 2026-05-26 |
| FL-1-5 | VPS smoke | `smoke_telegram_operator_vps.py` smoke_ok | Closed 2026-05-26 |
| FL-1-6 | Tests | focused 7 passed; full **1631 passed, 10 skipped** | Closed 2026-05-26 |
| FL-1-7 | Ops | Manual Telegram `/github` `/device` on phone | Closed 2026-05-26 |
| TG-GH-7-1 | Push translate | MyMemory via `TELEGRAM_PUSH_TRANSLATE=1` | Closed 2026-05-26 |
| TG-GH-7-2 | Scope | webhook/alert/digest only; not /github body | Closed 2026-05-26 |
| GI-G-3-5 | Account | No 模力方舟 free quota — phase cancelled | Cancelled 2026-05-26 |

## 2026-05-26 PE-C-1 Netdata MCP

| FL-1-8 | GI-G-3 re-probe | 3/3 resource_not_bound (2026-05-26) | Blocked |
| FL-1-9 | Acceptance smoke | `smoke_five_line_acceptance.py` acceptance_ok | Closed 2026-05-26 |
| FL-1-10 | Mirror lag fix | dual-push origin + branch resolve | Closed 2026-05-26 |

## 2026-05-26 CF-G-6 inventory weekly diff

| ID | Area | Evidence | Status |
|---|---|---|---|
| CF-G-6-1 | Code | `provider_inventory/weekly_diff.py` + digest line | Closed 2026-05-26 |
| CF-G-6-2 | Inventory hook | `run_cf_google_inventory.py` writes `inventory_weekly_diff.json` | Closed 2026-05-26 |
| CF-G-6-3 | VPS | CF 73 models; diff file on VPS; digest `collecting baseline` | Closed 2026-05-26 |
| CF-G-6-4 | Smoke | `smoke_weekly_inventory_vps.py` smoke_ok | Closed 2026-05-26 |
| CF-G-6-5 | Residual | Google fetch on VPS: Network unreachable | Open |

## 2026-05-26 TG-GH-6 deploy/smoke notify

| ID | Area | Evidence | Status |
|---|---|---|---|
| TG-GH-6-1 | Code | `deploy_common` + `notify_ops_telegram` + wire deploy/smoke scripts | Closed 2026-05-26 |
| TG-GH-6-2 | Import fix | VPS `scripts/` cwd → repo root on `sys.path` | Closed 2026-05-26 |
| TG-GH-6-3 | VPS deploy | `telegram_notify_deploy=ok notify_ok` | Closed 2026-05-26 |
| TG-GH-6-4 | VPS smoke | github_webhook + telegram_operator `telegram_notify_smoke=ok` | Closed 2026-05-26 |
| TG-GH-6-5 | Tests | `test_deploy_common.py` 4 passed | Closed 2026-05-26 |

## 2026-05-26 TG-GH-5 GitHub events

| ID | Area | Evidence | Status |
|---|---|---|---|
| TG-GH-5-1 | Format | issues + release + PR merged | Closed 2026-05-26 |
| TG-GH-5-2 | Auto task | `GITHUB_WEBHOOK_AUTO_TASK=0` default | Closed 2026-05-26 |
| TG-GH-5-3 | VPS | deploy + setup hook events; public push smoke 200 | Closed 2026-05-26 |
| TG-GH-5-4 | Tests | github webhook 20 passed; full 1636 | Closed 2026-05-26 |

## 2026-05-26 GI-G-3 Gitee AI adapter

| ID | Area | Evidence | Status |
|---|---|---|---|
| GI-G-3-1 | Inventory | `/models` 200 → 247 models, 89 chat candidates | Closed 2026-05-26 |
| GI-G-3-2 | Probe | 0/3 pass; all `resource_not_bound` | Blocked 2026-05-26 |
| GI-G-3-3 | Code | adapter + budget + admission overlay provider | Closed 2026-05-26 |
| GI-G-3-4 | VPS env | `deploy_gitee_ai_env.py`; `GITEE_AI_ENABLED=0` | Closed 2026-05-26 |
| GI-G-3-5 | Ops | Bind resource pack or use free-trial token in Gitee console | Open |

## 2026-05-26 TG-GH-3 unified digest

| ID | Area | Evidence | Status |
|---|---|---|---|
| TG-GH-3-1 | Module | `telegram_digest.py` + `webhook_activity_buffer.py` | Closed 2026-05-26 |
| TG-GH-3-2 | Routes | github/gitee webhook record activity; `_send_daily_digest` unified | Closed 2026-05-26 |
| TG-GH-3-3 | VPS deploy | `deploy_telegram_digest.py`; service active | Closed 2026-05-26 |
| TG-GH-3-4 | VPS smoke | `smoke_telegram_digest_vps.py` build OK; `--send` → True | Closed 2026-05-26 |
| TG-GH-3-5 | Tests | focused 3 passed; full **1618 passed, 10 skipped** | Closed 2026-05-26 |

## 2026-05-26 TG-GH-2 LiMa Code Telegram

| ID | Area | Evidence | Status |
|---|---|---|---|
| TG-GH-2-1 | Submodule | deepcode-cli `telegram-notifier.ts` 已有 | Closed 2026-05-26 |
| TG-GH-2-2 | Docs | `docs/TG_GH_2_LIMACODE_TELEGRAM.md` closeout | Closed 2026-05-26 |
| TG-GH-2-3 | E2E smoke | Windows worker `/lima task` → Telegram（待手工） | Open |

## 2026-05-26 TG-GH-1 reliability

| ID | Area | Evidence | Status |
|---|---|---|---|
| TG-GH-1-1 | VPS smoke | `deploy_reliability_ops.py` → `OK: http://127.0.0.1:7897: @limacode_bot` | Closed 2026-05-26 |
| TG-GH-1-2 | Ops | `LIMA_HEALTHCHECK_ENABLED` still 0 on VPS (dry-run ok) | Open |

## 2026-05-26 CQ-099 Code quality P2 long-function splits

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-099-1 | H1 anthropic_stream split | `anthropic_stream_sse/branches` + deps guard | Closed 2026-05-26 |
| CQ-099-2 | H2 device_gateway_ws split | `device_gateway_ws_handlers` per message type | Closed 2026-05-26 |
| CQ-099-3 | H4 streaming split | `streaming_bridge.py` owns sync bridge loop | Closed 2026-05-26 |
| CQ-099-4 | M1 scnet | `scnet_send_message()` extracted | Closed 2026-05-26 |
| CQ-099-5 | Tests | full **1546 passed, 10 skipped** | Closed 2026-05-26 |
| CQ-099-6 | Deferred | M2 narrow exceptions; M3 httpx migration for legacy router_http | Open |

## 2026-05-26 CQ-098 Security and quality review fixes

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-098-1 | P1 session memory DB path | `get_db_path()` resolves facade/env at call time; eval apply idempotency test passes | Closed 2026-05-26 |
| CQ-098-2 | P1 Telegram calculate | `lima_fc_tools/safe_math.py` bounded AST evaluator replaces `eval()` | Closed 2026-05-26 |
| CQ-098-3 | P1 admin retrain | async job id + lock + timeout via `asyncio.to_thread` | Closed 2026-05-26 |
| CQ-098-4 | P2 Telegram errors | `_operator_error(code)` generic chat messages | Closed 2026-05-26 |
| CQ-098-5 | P2 admin stats | `_backend_call_detail` normalization for legacy int counts | Closed 2026-05-26 |
| CQ-098-6 | Tests | full **1544 passed, 10 skipped** | Closed 2026-05-26 |

## 2026-05-26 CQ-097 Code review fixes (router_http dedup + legacy logging)

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-097-1 | HIGH dedup | `call_api()` uses `build_request_body(stream=False)` | Closed 2026-05-26 |
| CQ-097-2 | MEDIUM logging | `router_http` / `router_http_scnet` / `router_http_vision` use `_log` not `print` | Closed 2026-05-26 |
| CQ-097-3 | LOW constants | `router_http_body.UNAVAILABLE_USER_MESSAGE` shared by sync/stream/scnet | Closed 2026-05-26 |
| CQ-097-4 | Tests | **1539 passed, 10 skipped** (+1 authority on build_request_body delegation) | Closed 2026-05-26 |
| CQ-097-5 | Deferred | `anthropic_stream()` function length (~170 lines) — future P2 slice | Open |

## 2026-05-26 DG-DEPLOY-096 CQ-096 split deployed and verified on VPS

| ID | Area | Evidence | Status |
|---|---|---|---|
| DG-DEPLOY-096-1 | Deploy | `scripts/deploy_cq096_split.py` uploaded 7 files; `lima-router` active | Closed 2026-05-26 |
| DG-DEPLOY-096-2 | Loopback | VPS `curl :8080/device/v1/health` → redis backend, listener alive | Closed 2026-05-26 |
| DG-DEPLOY-096-3 | Public smoke post-deploy | `smoke_device_gateway_public.py` 4/4 (WSS drained=1 + full loop) | Closed 2026-05-26 |
| DG-DEPLOY-096-4 | Local tests | device_gateway routes + pipeline authority **29 passed** | Closed 2026-05-26 |

## 2026-05-26 DG-SMOKE-096 Device Gateway public path smoke

| ID | Area | Evidence | Status |
|---|---|---|---|
| DG-SMOKE-096-1 | Public health | `GET /device/v1/health` → `status=ok`, `task_store.backend=redis`, `session_bus.listener_alive=True` | Closed 2026-05-26 |
| DG-SMOKE-096-2 | Public HTTP | `POST /device/v1/tasks` + `/events` with `Bearer lima-local` → queued + motion_event_ack | Closed 2026-05-26 |
| DG-SMOKE-096-3 | Public WSS | fake-u8 `wss://chat.donglicao.com/device/v1/ws` full hello→motion→done loop; token from VPS `LIMA_DEVICE_TOKENS` | Closed 2026-05-26 |
| DG-SMOKE-096-4 | Smoke script | `scripts/smoke_device_gateway_public.py` 4/4; drain pending tasks before fake-u8 | Closed 2026-05-26 |

## 2026-05-26 CQ-091 Project memory detailed refresh

| ID | Area | Evidence | Status |
|---|---|---|---|
| MEM-091-1 | `docs/LIMA_MEMORY.md` | Agent 记忆索引 + 2026-05-26 consolidated state（微信退役、VPS、P0/P1.3、四线、REQUEST_PIPELINE、脚本表） | Closed |
| MEM-091-2 | `docs/TECHNICAL_ARCHITECTURE.md` | 「当前架构（2026-05-26）」节；历史商业图标注为过时参考 | Closed |
| MEM-091-3 | Test baseline | 沿用 `57ea35a`：**1530 passed, 10 skipped** | Closed |

## 2026-05-26 CQ-096 Code quality P2 device_gateway + router_http split

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-096-1 | P2.1 split | `device_gateway_dispatch/ws`, `router_http_{body,scnet,vision}` | Closed |
| CQ-096-2 | Tests | full **1538 passed, 10 skipped** | Closed |

## 2026-05-26 CQ-095 Code quality P2 split + pipeline authority tests

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-095-1 | P2.1 split | `code_orchestrator_context.py`, slim `code_orchestrator.py`, `routes/agent_task_evolution.py` | Closed |
| CQ-095-2 | P2.2/P2.3 | `tests/test_request_pipeline_authority.py`, `tests/README.md` | Closed |
| CQ-095-3 | Tests | full **1536 passed, 10 skipped** | Closed |

## 2026-05-26 CQ-094 Code quality P1.3 batch 4 (voice + channel + request tracking)

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-094-1 | P1.3 logging | `voice_gateway`, `approval_session`, `public_apis`, `media_inbound`, `request_tracking.get_ip_location` | Closed |
| CQ-094-2 | Tests | focused 41 passed; full **1530 passed, 10 skipped** | Closed |

## 2026-05-26 CQ-093 Code quality P1.3 batch 3 (agent_runtime + orchestrate)

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-093-1 | P1.3 logging | `agent_runtime/{real_executor,workspace_sandbox,tool_gateway_adapter,approval,events}`, `orchestrate.py`, `speculative.py`, `router_http.py` | Closed |
| CQ-093-2 | Tests | full **1530 passed, 10 skipped** | Closed |

## 2026-05-26 CQ-092 Code quality P1.3 batch 2 (streaming + audit)

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-092-1 | P1.3 logging | `streaming.py`, `anthropic_stream.py`, `chat_post_closeout.persist_session_memory`, `tool_gateway/audit.py`, `feature_flags.py`, `device_gateway/intent.py`, `routes/device_gateway.py` | Closed |
| CQ-092-2 | Tests | focused 85 passed; full **1530 passed, 10 skipped** | Closed |

## 2026-05-26 CQ-090 Code quality P1.3 batch + voice fail-closed

| ID | Area | Evidence | Status |
|---|---|---|---|
| CQ-090-1 | P1.3 logging | `media_inbound.py`, `health_recorder.py`, `chat_post_closeout.py`, `admin_api.py` | Closed |
| CQ-090-2 | `voice_call_live.html` | 禁止 `/api/live-key` 拼 WebSocket `?key=` | Closed |
| CQ-090-3 | Integration tests | `test_channel_gateway_integrations.py` 中文文案对齐 | Closed |
| CQ-090-4 | Git | `57ea35a` on `codex/free-web-ai-probe` | Closed |

## 2026-05-25 WeChat channel retired (repo + VPS hygiene)

| ID | Area | Evidence | Status |
|---|---|---|---|
| WX-RET-1 | Archive | `scripts/archive/wechat_retired/`；`docs/WECHAT_RETIRED.md` | Closed |
| WX-RET-2 | VPS | `cleanup_wechat_vps.py`；`find` 无 wechat/weixin 路径；`lima-router` health ok | Closed 2026-05-25 |
| WX-RET-3 | Local data | 删除 `data/wechat_install/`、`.geweapi_browser_profile/`、登录 QR 缓存；`.gitignore` 加固 | Closed 2026-05-25 |

## 2026-05-25 CQ-090 Channel Gateway G3 + Owner Digest（微信真机已退役，能力保留于 `/channel`）

> 产品通道：仅网页 `https://chat.donglicao.com`。微信方案见 `docs/WECHAT_RETIRED.md`。

| ID | Area | Evidence | Status |
|---|---|---|---|
| WX-090-1 | Extra APIs | calc/holiday/stock/earthquake + quotas | Implemented + unit tests |
| WX-090-2 | Multi-turn | `channel_chat_turns` + `ChannelChatSession` + reset clears | Implemented |
| WX-090-3 | Owner | `/简报` `/github` owner-only; digest uses public weather + status | Implemented |
| WX-090-4 | Smoke | `smoke_wechat_channel_gateway.py` steps 15–17; test inject_deps order fixed | Passed locally |
| WX-090-5 | VPS | `scripts/deploy_channel_gateway.py --smoke` on `47.112.162.80`; health/menu/calc/chat_turn passed | Closed 2026-05-25 |

## 2026-05-25 CQ-089 Channel Public Tools（历史标签 WeChat，实现为 channel_gateway）

| ID | Area | Evidence | Status |
|---|---|---|---|
| WX-089-1 | Tool surface | 11 intents + 中英命令别名；`channel_tools` / `public_apis` / `tool_usage` | Implemented |
| WX-089-2 | Quota | `channel_tool_usage` per hash/tool/day; guest limits + owner mult | Implemented + tests |
| WX-089-3 | Search/read | `search_gateway` when `TINYFISH_API_KEY`; DDG + simple HTML fallback | Implemented |
| WX-089-4 | Next | 已由 CQ-090 覆盖（G3/主人/VPS smoke） | Superseded → Closed 2026-05-25 |

## 2026-05-25 CQ-088 Channel Zero-Friction Bind（历史标签 WeChat）

| ID | Area | Evidence | Status |
|---|---|---|---|
| WX-088-1 | Auto guest bind | `ensure_guest_binding()` + `handle_message` 对 unbound/revoked 非 `/bind` 自动开通；首绑欢迎语 `_WELCOME_GUEST` | Implemented; 75 focused tests passed |
| WX-088-2 | Env toggle | `LIMA_CHANNEL_AUTO_GUEST_BIND=0` 恢复「需先绑定」；须运行时读 env（非 import 时常量） | Fixed + regression tests |
| WX-088-3 | Revoked re-entry | `ensure_guest_binding` 对 REVOKED 行 reactivate 而非 INSERT 失败 | Fixed + store test |
| WX-088-4 | Next slice | 已由 CQ-089 覆盖（公开工具/配额/search_gateway） | Superseded → Closed 2026-05-25 |

## 2026-05-25 XianyuAutoAgent Reference Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| XAA-001 | Reference value | `XianyuAgent.py` shows rules-plus-LLM intent routing and specialist agents; `context_manager.py` stores chat history and counters; `main.py` manages WebSocket heartbeat, reconnect, token refresh, ACK, and manual takeover. | Borrow the production shape through LiMa-owned interfaces only. |
| XAA-002 | License boundary | The observed repository license is GPL-3.0. | Do not copy source, prompts, protocol handlers, or request shapes into LiMa. |
| XAA-003 | Platform boundary | The connector path uses cookies and private platform protocol details. | Keep WeChat/social connectors default-off behind owner, credential, platform-term, rate-limit, audit, and stop-switch gates. |
| XAA-004 | LiMa adaptation | The useful LiMa shape is `ChannelConnector -> SessionStore -> IntentRouter -> ExpertAgent -> HumanTakeover -> AuditLog -> TaskQueue`. | Start with a fake connector and productive flows before adding real messaging bridges. |
| XAA-005 | Priority | Messaging bridges are less urgent than observable hardware and coding execution. | Keep P0.2 real Device Gateway path/text/SVG pipeline ahead of WeChat/Xianyu-style connector work. |

## 2026-05-25 P0.4/P0.5/P0.7 Review Findings

| ID | Area | Evidence | Status |
|---|---|---|---|
| P04-review-1 | Preview replay artifact | `create_task_from_transcript("write LiMa")` produced a `preview_svg` truncated to 120 chars by `validate_capability_params()`, so the task record did not contain a complete `</svg>` preview. | Fixed: `preview_svg` is preserved up to 4096 chars; regression test asserts SVG starts with `<svg` and ends with `</svg>`. |
| P05-review-1 | Control intent execution | `resolve_voice_task("home")` parsed correctly, but `project_to_motion_task()` turned control capabilities into failed `run_path` placeholders with `E_UNSUPPORTED_CAPABILITY`. | Fixed: `home/pause/resume/stop/get_device_info` are motion-family capabilities and create control `motion_task` payloads without path requirements. |
| P07-review-1 | Ops metrics endpoint crash | `/v1/ops/metrics` used `getattr(request.app, "state", {}).get(...)`; Starlette `State` has no `.get()`, so authenticated requests raised 500. | Fixed: reads `request.app.state.stats` safely; regression test covers authenticated 200 response. |
| P07-review-2 | Ops metrics empty stats | `server.py` kept `_stats` as a module global but did not expose it on `app.state`, so the new ops endpoint would report zeros even after the crash fix. | Fixed: `app.state.stats = _stats`; regression test asserts Server exposes the live stats object. |

## 2026-05-25 P0.1 ESP32 Motion Executor Contract — Implementation Closeout

| ID | Area | Evidence | Status |
|---|---|---|---|
| P0.1-S1 | Server error codes + protocol | `protocol_families.py` MotionErrorCode (8 codes), `protocol.py` motion_failure_event() + validate_motion_task_lifecycle(), fake-U8 --test failure mode | Implemented / 38 focused tests passed |
| P0.1-S2 | Device Gateway path validation | `path_validator.py` with capability/path/feed/bounds validation wired into tasks.project_to_motion_task() | Implemented / 33 focused tests passed |
| P0.1-S3 | ESP32 default board fail-loud | `board.cc` HandleMotionTaskJson() now emits E_UNSUPPORTED_BOARD; `board.h` SupportsMotionTask() virtual added | Implemented / ESP32 firmware compile passed; hardware flash pending |
| P0.1-S4 | Zhuguang board failure hardening | Missing capability, missing path, unsupported capability paths now emit structured failure events via EmitMotionEventError() | Implemented / ESP32 firmware compile passed; hardware flash pending |
| P0.1-S5 | VPS deployment | Service uses `/usr/local/bin/python3.10` even though system `python3` is 3.6.8; deploy backup `/opt/lima-router/backups/p01-motion-contract-20260525_072701/runtime-before.tgz`; public smoke `12/12`; fake-U8 WSS success/failure passed | Closed |
| P0.1-review-1 | Motion failure error preservation | Server originally dropped nested `error` and firmware `error_code`/`error_message` during `validate_motion_event()` normalization. | Fixed in `4a7faed`; task snapshots now retain normalized `error.code`/`error.reason`. |
| P0.1-review-2 | Invalid task queueing | Server-side validation failures were marked failed but `/device/v1/tasks` / WebSocket transcript paths could still queue or dispatch them. | Fixed in `4a7faed`; invalid tasks return `status=failed` or `motion_task_failed` without queueing/dispatch. |
| P0.1-review-3 | fake-U8 WSS compatibility | Local `websockets==15.0.1` uses `additional_headers`, while fake-U8 used old `extra_headers`. | Fixed in esp32S_XYZ `160e526`; tests cover both APIs. |
| P0.1-regression | Full suite | 1218 passed, 8 skipped after review fixes | Passed |

## 2026-05-25 Productivity Infrastructure Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| PROD-001 | Global constraint | `AGENTS.md` now states that all work must serve real productivity, productization, and LiMa's own distinctive character. | Use this as the filter for every plan/review: useful execution beats decorative features. |
| PROD-002 | ESP32 silent no-op risk | `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/common/board.cc` default HandleMotionTaskJson() now sends E_UNSUPPORTED_BOARD failure event. | Closed by P0.1-S3. |
| PROD-003 | ESP32 failure telemetry | `E_MISSING_PATH` / unsupported-capability style failures and firmware compile are now covered; real hardware is not flashed yet. | Hardware flash and real-device smoke coverage. |
| PROD-004 | Device task intelligence | The text/SVG/path pipeline is implemented with stroke font, SVG parser, preview, and safety limits. | Keep fake-U8/VPS smoke in the release gate and expand fixtures from real operator commands. |
| PROD-005 | Intent parsing | Deterministic regex parsing, confidence, rejection reasons, and gated LLM replanning are implemented. | Feed accepted/rejected outcomes into the later learning loop. |
| PROD-006 | LiMa Code workflow depth | `deepcode-cli` now writes artifact bundles under `.lima/artifacts/<task_id>/` for `/lima plan`, `/lima test`, `/lima review`, and `/lima ship`. | Closed for artifact bundle; use these artifacts as PROD-008 learning-loop evidence before broad autonomy. |
| PROD-007 | Observability access | Authenticated `/v1/ops/metrics` is deployed and smoke-verified with production-shaped backend stats. | Add deeper request_id/task_id/device_id/session_id correlation as incidents expose gaps. |
| PROD-008 | Learning loop | Memory, eval, routing, and prompt components exist but are not yet one outcome-driven feedback loop. | Promote verified task outcomes into memory/prompt/routing eval candidates with rollback evidence. |

## Production Topology

- VPS: `47.112.162.80`
- Public chat: `https://chat.donglicao.com`
- Public open platform: `https://api.donglicao.com`
- nginx listens on 80/443.
- `lima-router` listens on `127.0.0.1:8080`.
- New API listens on `127.0.0.1:3003`.
- Voice gateway listens on `127.0.0.1:8091`.
- nginx routes chat `/v1/` to `127.0.0.1:8080`.
- nginx routes chat `/ws/voice` to `127.0.0.1:8091`.
- nginx routes open platform to `127.0.0.1:3003`.

## M0 Implementation (2026-05-24)

- Created `docs/DEVELOPER_CHECKLIST.md` — test commands for all 12 areas
- Created `docs/REVIEW_PACKET_TEMPLATE.md` — standard slice review packet
- Updated `task_plan.md` with 13-milestone tracking table
- Recorded 31 untracked files as out-of-scope
- Test baseline: all area-specific commands documented; 2 known pre-existing failures in test_routing_engine.py

## Verified Working

- Chat homepage returns 200.
- Chat frontend `/app.js` returns 200 and uses `/v1/chat/completions` with `stream: true`.
- Chat API non-streaming request returns 200 with assistant content.
- Chat API streaming request returns 200 with SSE chunks.
- Open platform homepage returns 200.
- Open platform unauthenticated `/v1/models` returns 401.
- Open platform database exists at `/opt/new-api/one-api.db`.
- New API has two enabled channels pointing at `http://localhost:8080`.
- New API has enabled tokens available.
- Open platform local and public `/v1/models` pass with an enabled token.
- Open platform local and public `/v1/chat/completions` pass with an enabled token.
- Chat and API TLS certificates are valid through 2026-08-16.
- Chat and API pages return `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy`.
- Chat `/quickstart/` and nested quickstart paths now redirect to `/` instead of serving HTML as JS/CSS.
- Open platform title now renders as `LiMa AI - 开放平台`.
- Public direct access to internal ports `3000`, `3001`, `3003`, `8080`, and `8091` is blocked; VPS localhost checks for `8080` and `3003` still pass.
- New API database backup exists at `/opt/new-api/backups/one-api-20260522-151608.db`, and cron now writes dated files with 14-day retention.

## Direction Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| PCA-001 | Product direction | Public commercial platform work started before real private usage feedback. | Use `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` as active plan. |
| PCA-002 | Backend quality | Model catalog contains coding hints, but no current same-fixture backend ranking. | Add coding fixtures and score candidates. |
| PCA-003 | Runtime routing | Router has many pools and fallbacks from broader experiments. | Keep only coding-relevant tiers once ranking exists. |
| PCA-004 | VPS safety | Firewall and HTTPS hardening already help private use. | Retain those low-cost protections. |

## Coding Backend Evaluation Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| CBE-001 | Broad smoke | 85 coding-like candidates were tested on `code_review`; 16 passed. | Use this as the first wide filter before full fixture runs. |
| CBE-002 | Full fixture winners | `scnet_large_ds_flash`, `github_gpt4o`, `github_gpt4o_mini`, and `or_gptoss_120b` passed all three fixtures. | Put these in strong/default coding tiers, with `or_gptoss_120b` later because it is slow. |
| CBE-003 | Fast usable tier | `cerebras_gptoss`, `groq_gptoss`, and `mistral_small` scored 80+ average with sub-800ms average latency. | Use these for simple or latency-sensitive coding traffic. |
| CBE-004 | Partial but useful tier | `mistral_pixtral`, `mistral_large`, `mistral_devstral`, `github_codestral`, `mistral_medium`, and `featherless` passed 2/3 fixtures. | Keep as fallback or specialized coding candidates, but avoid strict JSON/tool-output routing first. |
| CBE-005 | Failure classes | Many providers failed with local WinError 10013, HTTP 401, HTTP 429, HTTP 500, or timeout/cooldown. | Re-test after fixing keys, rate limits, or local socket policy. |
| CBE-006 | IDE routing | Local `routing_engine.route(..., ide_source="Continue")` classified the request as coding and selected `scnet_large_ds_flash` successfully. | Next verification should hit `https://api.donglicao.com` from a real IDE/agent client. |

## Context Engineering Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| CTX-001 | Cursor/Codex/Claude Code lesson | The useful shared pattern is compact context engineering, not larger generic prompts. | Keep request-local context digest small and evidence-based. |
| CTX-002 | VPS boundary | LiMa cannot read the user's local IDE workspace from the VPS. | Only summarize request text, system prompt hints, file paths, tool results, and error signals already sent by the client. |
| CTX-003 | Closed | Claude Code `/v1/messages` tool routes now inject LiMa context preflight for Tier-1 OpenAI msgs and Tier-2 Anthropic-native bodies via `inject_anthropic_body_preflight`. Tests in `tests/test_anthropic_preflight.py`. | None. |
| CTX-004 | Verification | Local suite returned `70 passed`; public `/v1/messages` tool smoke returned 200 in 489ms with `stop_reason=tool_use`. | Use a real IDE session next to judge subjective coding experience and latency. |

## Free Model Routing Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| FREE-001 | SCNet direct models | VPS smoke passed for `scnet_ds_flash` (2904ms), `scnet_ds_pro` (26496ms), `scnet_qwen235b` (2110ms), and `scnet_qwen30b` (1727ms). | Use these as active free fallback capacity; keep `scnet_ds_pro` deep because it is slow. |
| FREE-002 | SCNet local large proxy | `scnet_large_ds_flash` and `scnet_large_ds_pro` returned connection refused on VPS `localhost:4505`, but that was the wrong health signal. Windows `4505` is running and chat-compatible. | Keep registered; re-run fixtures through Windows `8080` or VPS `8088` FRP path before promotion. |
| FREE-003 | SCNet minimax | `scnet_minimax` timed out after ~30s. | Do not include in default active pools. |
| FREE-004 | Kimi CF | `cf_kimi_k26` returned successfully but took ~9987ms and did not obey the tiny smoke prompt tightly. | Keep as chat/fallback capacity, not low-latency coding primary. |
| FREE-005 | Kimi local/stock | Windows `4504` is running, but chat returns `chat.anonymous_usage_exceeded`; `stock_kimi_k2` returned invalid response. | Mark local Kimi as manual-refresh/quota-exhausted instead of hot-path retrying it. |
| FREE-006 | Route update | `code_orchestrator.py` and `router_v3.py` now include VPS-working SCNet direct models in active pools. | Re-run coding fixtures from VPS if these become candidates for primary coding. |
| FREE-007 | Deploy behavior | `systemctl restart lima-router` can hang while uvicorn waits for existing `/v1/messages` connections to close. | If restart sticks in `deactivating`, use `systemctl kill -s SIGKILL lima-router`, `systemctl reset-failed lima-router`, then `systemctl start lima-router`. |
| FREE-008 | SCNet first-tier eval | VPS three-case coding eval passed for `scnet_ds_flash` (3/3, 3330ms avg), `scnet_qwen235b` (3/3, 4004ms avg), `scnet_qwen30b` (3/3, 2713ms avg), and `scnet_ds_pro` (3/3, 4571ms avg). | Promote these direct SCNet models into coding first tier. |
| FREE-009 | Kimi first-tier eval | `cf_kimi_k26` passed only 1/3 fixtures with 7844ms avg; local Kimi proxy models refused port `4504`; `stock_kimi_k2` returned invalid response. | Keep Kimi out of first tier until proxy/format issues are fixed. |
| FREE-010 | SCNet first-tier deployment | VPS route order now starts `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, `github_gpt4o`; public coding smoke returned 200 in 3347ms. | Keep monitoring real IDE latency and fallback behavior. |
| FREE-011 | FRP closure | `frpc.exe` registers `redcode-api`; VPS `8088` reaches Windows LiMa `8080`; public `/health`, `/v1/models`, and `/v1/chat/completions` return 200. | Treat `http://47.112.162.80:8088/v1` as the direct validation path for local-router and Windows proxy behavior. |
| FREE-012 | Free web AI expansion | Duck.ai and HeckAI-style no-login web AI sources can add capacity, but undocumented web protocols and rate limits are fragile. | Add a candidate registry and sandbox probe harness before any routing integration. |
| FREE-013 | Routing efficiency | Static ordering wastes free quota and can retry known-bad sessions. | Add token/session state, quota cooldown, and quality/latency/quota/task-fit scoring. |
| FREE-014 | Candidate reachability | Duck.ai, HeckAI, HIX Chat, GPT.chat, deep-seek mirror, and PLAI.chat pages returned HTTP 200 in the first harmless reachability probe. | Treat this as page reachability only; next step is protocol/request-shape discovery with harmless prompts. |
| FREE-015 | Backend failure state | `health_tracker.py` can now classify manual refresh, quota exhausted, rate limited, auth expired, timeout, and provider error states. | Use these states in Task 4 route scoring/skipping. |
| FREE-016 | DuckAI reverse state | `D:\duckai` already reverse-engineers DuckAI and local `4500` passes `/v1/models` plus user-only chat. | Stop treating DuckAI as net-new research; fix LiMa request format and tunnel. |
| FREE-017 | DuckAI LiMa blocker | Local DuckAI fails with upstream 400 when the request contains an empty OpenAI `system` message; `http_caller.py` currently prepends one for OpenAI backends. | Add provider-specific `no_system` request construction and tests. |
| FREE-018 | Existing adapter drafts | `D:\ollama_server\heckai-worker.js` and `umint_proxy.js` already exist. | Smoke existing drafts before doing new browser reverse work. |
| FREE-019 | Page-only candidates | HIX Chat, GPT.chat, Deep-seek mirror, and PLAI.chat have reachability only, no local API adapter. | Keep out of routing and defer until already-reversed assets are stable. |
| FREE-020 | DuckAI no-system fix | DuckAI accepts LiMa calls once OpenAI `no_system` omits the synthetic system role and preserves context in the user message. | Keep provider flag covered by `test_http_caller.py`. |
| FREE-021 | DuckAI admission | Local three-case eval passed 3/3 for `ddg_gpt4o_mini` and `ddg_gpt5_mini`; Haiku failed strict JSON; Tinfoil GPT-OSS returned 500/cooldown. | Keep winners late fallback until tunnel and stability work close. |
| FREE-022 | SCNet-large local eval | Both `scnet_large_ds_flash` and `scnet_large_ds_pro` passed 3/3 locally; flash averaged 987ms. | Add a topology-aware promotion path instead of making VPS try Windows-local `4505`. |
| FREE-023 | Refresh log safety | Kimi/TheOldLLM refresh scripts/logs can emit token fragments while Kimi still needs manual refresh and OldLLM still times out. | Redact refresh output before active token refresh work. |

## Latest Deployment Verification

- 2026-05-22 coding-routing deploy uploaded `router_v3.py`, `routing_engine.py`, and `code_orchestrator.py` to `/opt/lima-router`.
- The pre-restart remote compile check covered the three uploaded files plus `server.py`.
- `systemctl restart lima-router` succeeded.
- VPS-local `/health` returned 200 after restart.
- VPS-local coding smoke returned 200 with backend metadata for `github_gpt4o`.
- Public chat API smoke returned 200 with backend metadata for `cerebras_gptoss`.
- Rollback source for the uploaded files is `/opt/lima-router/backups/deploy-20260522_175739`.

## Latest Context Preflight Deployment

- 2026-05-22 context-preflight deploy uploaded `server.py`, `code_orchestrator.py`, and `lima_context.py` to `/opt/lima-router`.
- Rollback source for this deploy is `/opt/lima-router/backups/context-preflight-20260522_183133`.
- Final sync rollback source for no-BOM `code_orchestrator.py` is `/opt/lima-router/backups/context-preflight-sync-20260522_183423`.
- Remote compile passed for `server.py`, `code_orchestrator.py`, and `lima_context.py`.
- `systemctl restart lima-router` completed.
- VPS-local `/health` returned 200.
- Final public `https://chat.donglicao.com/v1/messages` Anthropic tool smoke returned 200 in 600ms with `stop_reason=tool_use`.

## Latest Free Model Routing Deployment

- 2026-05-22 free-model routing deploy uploaded `code_orchestrator.py` and `router_v3.py` to `/opt/lima-router`.
- Rollback source: `/opt/lima-router/backups/free-model-routing-20260522_184556`.
- Local verification before deployment returned `71 passed in 0.52s`.
- Remote compile passed for `server.py`, `routing_engine.py`, `code_orchestrator.py`, and `router_v3.py`.
- Restart initially hung in `deactivating` because uvicorn waited for open connections; SIGKILL/start recovery restored service.
- VPS-local `/health` returned 200.
- Public coding smoke returned 200 in 4585ms.
- Public Anthropic tool smoke returned 200 in 672ms with `stop_reason=tool_use`.

## Latest SCNet First-Tier Deployment

- 2026-05-22 SCNet first-tier deploy uploaded `code_orchestrator.py` and `router_v3.py` to `/opt/lima-router`.
- Rollback source: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`.
- Local verification before deployment returned `71 passed in 0.59s`.
- Remote compile passed for `server.py`, `routing_engine.py`, `code_orchestrator.py`, and `router_v3.py`.
- `lima-router` restarted cleanly and VPS-local `/health` returned 200.
- VPS route-order smoke confirmed coding selection starts with `scnet_ds_flash`, `scnet_qwen235b`, `scnet_qwen30b`, `scnet_ds_pro`, then `github_gpt4o`.
- Public coding smoke returned 200 in 3347ms.

## Latest Cloudflare Routing Deployment

- 2026-05-22 Cloudflare routing deploy uploaded `backends.py`, `router_v3.py`, and `code_orchestrator.py` to `/opt/lima-router`.
- Rollback source: `/opt/lima-router/backups/cloudflare-routing-20260522_210441`.
- Remote compile passed for `server.py`, `routing_engine.py`, `backends.py`, `router_v3.py`, and `code_orchestrator.py`.
- `lima-router` restarted and VPS-local `/health` returned 200.
- VPS route-order probe confirmed the default code selection window includes `cf_qwen_coder` and `cfai_qwen_coder`.
- VPS direct account Cloudflare smoke returned `cf-direct-ok` through `cf_qwen_coder`.
- VPS Worker Cloudflare smoke returned `cfai-ok` through `cfai_qwen_coder`.
- Public primary `/v1/models` and `/v1/chat/completions` returned 200 after deployment.

## Latest Token-Safe Local Proxy Routing Increment

- Added `runtime_topology.py` so local-only backends are active only when local proxies are explicitly enabled, a tunnel override exists, or the expected local port is reachable.
- `router_v3.py` and `code_orchestrator.py` now filter local-only backends before selection/execution.
- Added tests proving `scnet_large_ds_flash` is blocked when local proxy topology is unavailable and allowed when explicitly enabled.
- `D:\ollama_server` refresh scripts were redacted in-place:
  - `secret_redactor.js` added.
  - Kimi/TheOldLLM refresh scripts no longer rely on hardcoded Cloudflare API token fallbacks.
  - TheOldLLM proxy no longer embeds a request token literal.
  - Refresh server no longer returns raw token values.
- Verification: Python compile passed, focused suite returned `70 passed`, Node syntax checks passed, and redactor sample check passed.
- Refresh was intentionally not executed during this pass.
- VPS deployment backups:
  - `/opt/lima-router/backups/topology-guard-20260522_211850`
  - `/opt/lima-router/backups/short-answer-hotfix-20260522_212816`
  - `/opt/lima-router/backups/exact-output-quality-20260522_212959`
- Production verification exposed a server-level quality gate bug: exact short answers were rejected as low quality, causing false `fallback_exhausted`.
- `server.py` now uses query-aware exact-output checks:
  - short exact-output answers such as `topology-ok` are allowed;
  - non-matching long answers to `Return exactly: ...` are rejected.
- Final verification: local compile passed, focused suite returned `73 passed`, public `/v1/chat/completions` returned exact `topology-ok`, public `/v1/messages` returned exact `ide-ok`, and FRP `8088` health returned 200.

## Production Safety Changes Retained

- Backed up `/etc/nginx/conf.d/chat.donglicao.com.conf` and `/etc/nginx/conf.d/donglicao.conf` with `commercial-audit` timestamp suffixes.
- Backed up `/opt/new-api/one-api.db` to `/opt/new-api/backups/one-api-20260522-151608.db`.
- Added basic security headers to chat/API nginx configs.
- Fixed API nginx title replacement from mojibake to Chinese text.
- Added chat `/quickstart` and `/quickstart/` redirect to `/`.
- Removed firewalld public ports `8080/tcp` and `3001/tcp`.
- Added `eth0`-scoped firewalld direct reject rules for `3000`, `3001`, `3003`, `8080`, and `8091`.
- Replaced fixed-date New API backup cron with dated backup plus 14-day retention.
- These safety changes are kept even though public commercial rollout is paused.

## Latest Website Verification

- `https://chat.donglicao.com/`: 200, title `LiMa AI - 智能编程助手`, basic security headers present.
- `https://api.donglicao.com/`: 200, title `LiMa AI - 开放平台`, basic security headers present.
- `https://chat.donglicao.com/v1/chat/completions`: non-streaming 200 and streaming 200.
- `https://api.donglicao.com/v1/models`: 200 with valid New API token.
- `https://api.donglicao.com/v1/chat/completions`: 200 with valid New API token.
- `http://47.112.162.80:3000`, `3001`, `3003`, `8080`, `8091`: public direct attempts fail.
- `http://127.0.0.1:8080/health` and `http://127.0.0.1:3003/v1/models`: still pass on VPS localhost.

## 2026-05-25 P0.4/P0.5/P0.7 Deploy Findings

| ID | Area | Evidence | Resolution |
|---|---|---|---|
| PROD-009 | Ops metrics production stats shape | VPS authenticated `/v1/ops/metrics` returned HTTP 500 after deploy. Journal showed `TypeError: bad operand type for unary -: 'dict'` at backend call sorting because production `backend_calls` values are `{count, success, total_ms}` dicts. | `routes/ops_metrics.py` now normalizes numeric and dict stats, keeps compact `backend_calls`, and adds `backend_call_details`. Regression test added; VPS-local and public ops metrics now return HTTP 200. |
| PROD-010 | Smoke cleanup hygiene | Device Gateway HTTP smoke creates pending Redis tasks when no test device is connected. | Used temporary `device_id=codex-smoke-p04` and deleted its pending/processing queues after verification. |

Latest P0.4/P0.5/P0.7 verification:

- Focused local tests: `31 passed`.
- Public online distribution smoke: `12/12 checks passed`.
- Public `/v1/ops/metrics`: HTTP 200 with `backend_calls` and
  `backend_call_details`.
- Device task smoke: `write LiMa` preserves a complete `preview_svg`; `home`
  returns `capability=home` without error.

## 2026-05-23 Reference Architecture Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| REF-001 | OpenRAG | OpenRAG is a full document RAG platform with ingestion, retrieval, MCP, and heavier backing services. | Borrow ingestion/retrieval-trace ideas; do not adopt the whole stack. |
| REF-002 | Always-on memory | Google Cloud always-on-memory-agent matches LiMa's Session Memory direction: SQLite, inbox ingestion, background consolidation, memory query. | Use it as the main pattern for LiMa's memory daemon. |
| REF-003 | Retrieval hot path | Closed by CQ-059: `context_pipeline/retrieval_injection.py` is the single authority with trace evidence. | None for this slice. |
| REF-004 | Memory hot path | `server.py` saves memories and triggers compaction; `session_memory.processor` recall is tested but not the main `server.py` path. | Add typed recall and keep expensive consolidation outside the request. |
| REF-005 | Pipeline shape | Documented in `docs/REQUEST_PIPELINE_AUTHORITY.md`: production uses explicit integration blocks; `build_default_pipeline()` is lab-only. | Revisit when `server.py` is modular enough for factory parity tests. |
| REF-006 | Key scheduling | `ConcurrencyPool` is implemented and tested but has not replaced `key_pool.py`. | Integrate only if provider-key concurrency becomes a real bottleneck. |

Latest local verification:

- LiMa target suite: `382 passed, 8 skipped`.
- Latest checked commit: `8b86228`.
- New doc: `docs/REFERENCE_PROJECT_EVALUATION.md`.

## 2026-05-23 Agent Autonomy Reference Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| AGENT-001 | OpenAI Agents SDK | Current public README describes a lightweight multi-agent workflow framework with agents, tools, guardrails, sessions, tracing, handoffs, human-in-the-loop, and sandbox agents. | Borrow role contracts, handoffs, guardrails, sessions, tracing, and sandbox-boundary ideas; do not replace LiMa routing wholesale. |
| AGENT-002 | Google ADK | Current ADK 2.0 README highlights a code-first framework plus workflow runtime with graph execution, routing, fan-out/fan-in, loops, retry, state, dynamic nodes, human-in-the-loop, and nested workflows. | Treat ADK as the strongest workflow-runtime reference for LiMa's future agent DAG. |
| AGENT-003 | GenericAgent | README describes a minimal loop, layered memory, nine atomic tools, and skill crystallization after successful tasks. | Borrow layered memory and skill crystallization; do not enable arbitrary system control or package installation by default. |
| AGENT-004 | EvoMap Evolver | README describes Genes/Capsules/Events, GEP protocol, local asset stores, validation, and environment-agnostic operation. | Borrow compact auditable evolution assets and validation-before-promotion; keep external worker networks disabled. |
| AGENT-005 | Agency Agents | README describes a large library of specialized agent personalities with workflows, deliverables, and success metrics. | Borrow role-spec style and success metrics; do not start with dozens of persona agents. |
| AGENT-006 | LiMa fit | LiMa already has routing, memory writes, retrieval primitives, tool gateway, tests, and deployment discipline. | Build a five-agent local loop first: Planner, Coder, Reviewer, Tester, Memory/Evolution. |

## 2026-05-23 TechSpar Reference Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| TECHSPAR-001 | Product loop | TechSpar README frames the product as one loop over long-term memory, profile update, mastery, and next-round scheduling rather than isolated interview pages. | Borrow the loop shape for LiMa coding tasks, reviews, tests, routing failures, and deployments. |
| TECHSPAR-002 | Dynamic training base | TechSpar combines knowledge base, frequent questions, history, weak points, and mastery to decide what to train next. | Adapt to dynamic test/review focus from risky modules and repeated failures. |
| TECHSPAR-003 | Write-back after each round | TechSpar writes per-question evaluation, weak points, strengths, behavior traits, mastery, long-term profile, and SM-2 scheduling after training. | Add LiMa mastery events, module profiles, weak points, and regression scheduling. |
| TECHSPAR-004 | Graph/diagnostic value | TechSpar's graph concept is useful as a way to inspect related weak points and low-score areas. | Add admin diagnostics later; do not build a React product shell first. |
| TECHSPAR-005 | License boundary | TechSpar uses CC BY-NC 4.0. | Borrow concepts only; do not copy code into LiMa without a separate license review. |

## 2026-05-23 LiMa Code Integration Findings

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| LIMACODE-001 | Fork | Owner forked LiMa Code to `https://github.com/zhuguang-ZFG/deepcode-cli.git`. | Clone the fork into `D:\GIT\deepcode-cli`. |
| LIMACODE-002 | Product fit | LiMa Code is better suited as LiMa's visible vibe coding shell/worker than as a hidden backend-only module. | Point LiMa Code provider config at LiMa's OpenAI-compatible endpoint first. |
| LIMACODE-003 | Safety | The current LiMa workspace is dirty and contains many reference repos and local experiments. | Do not run LiMa Code directly against `D:\GIT`; use sandbox or worktree first. |
| LIMACODE-004 | Integration boundary | LiMa should keep routing, memory, mastery, safety, and final verification; LiMa Code should own task UX and coding workflow. | Build a LiMa Code LiMa profile before deeper code changes. |
| LIMACODE-005 | Local clone | Fork cloned successfully to `D:\GIT\deepcode-cli`; branch is `main...origin/main`. | Keep LiMa Code work isolated in that repo. |
| LIMACODE-006 | Runtime stack | `package.json` identifies a TypeScript/npm CLI package `@vegamo/deepcode-cli`, Node `>=22`, build via `npm run build`, tests via `npm test`. | Install dependencies before TypeScript/runtime changes. |
| LIMACODE-007 | Provider config | README and configuration docs support OpenAI-compatible models through `MODEL`, `BASE_URL`, and `API_KEY`; env overrides use `DEEPCODE_*`. | LiMa can be configured without code changes. |
| LIMACODE-008 | Tool risk | Built-in tools include `bash`, `read`, `write`, `edit`, `AskUserQuestion`, `UpdatePlan`, and `WebSearch`; `bash` executes local shell commands. | Add safety boundaries before using on real LiMa workspace. |
| LIMACODE-009 | First fork changes | Added `docs/lima.md`, `docs/lima_zh_CN.md`, and README links for LiMa provider configuration and safe first-run guidance. | Next step is dependency install and sandbox smoke. |
| LIMACODE-010 | Rebrand | User-facing name is now LiMa Code and the promoted command is `lima-code`. `.deepcode` storage and `DEEPCODE_*` env vars remain legacy-compatible. | Add a tested `.lima-code` / `LIMA_CODE_*` migration in a later slice. |
| LIMACODE-011 | Native config | `.lima-code` settings and `LIMA_CODE_*` env vars are now native and preferred; `.deepcode` and `DEEPCODE_*` remain fallback-compatible. | Next slice can move session/log/storage paths after deciding migration behavior. |

## 2026-05-23 Code Quality Review Findings

Source record: `docs/superpowers/plans/2026-05-23-code-quality-review-closeout.md`.

| ID | Area | Evidence | Next Action |
|---|---|---|---|
| CQ-001 | Test baseline | `python -m pytest -q --ignore=active_model` currently fails during collection because `tests/test_agent_task_routes.py` imports removed `_events` and `_tasks` symbols from `routes.agent_tasks`. | Restore the route-test contract against the current `_TaskStore` implementation or add a test reset helper. |
| CQ-002 | Agent task concurrency | `/agent/tasks/{task_id}/claim` can reclaim `running` tasks and overwrite worker lease metadata. | Make claim atomic and reject active running leases with 409. |
| CQ-003 | Admin security | `routes/admin.py` still supports `?token=` and injects `_ADMIN_TOKEN` into browser JavaScript. | Move admin UI to HttpOnly Secure session cookies and stop exposing the long-lived admin token to JS/query strings. |
| CQ-004 | Private API boundary | `/v1/models` is unauthenticated while chat/message endpoints require the private API key. | Decide whether IDE discovery requires an open model list; otherwise apply the same private guard. |
| CQ-005 | Config drift | `backends.py` defines `THINKING_BACKENDS` twice and the later definition drops `longcat_web_think`. | Collapse capability lists to one source and add a regression test. |
| CQ-006 | Retrieval duplication | `routing_engine.py` has inline retrieval injection and an overlapping `inject_retrieval_context()` helper. | Keep one retrieval injection path and test trace output. |
| CQ-007 | File-size pressure | `smart_router.py`, `server.py`, `routing_engine.py`, and `http_caller.py` exceed the 300-line project target. | Continue decomposition after P0 safety/test fixes are green. |
| CQ-008 | Repository hygiene | `git status --short` shows many untracked reference repos, scripts, local data, and generated files. | Tighten ignore rules and use a commit checklist before production commits. |

## 2026-05-23 Code Quality Review Implementation Follow-Up

| ID | Status | Evidence | Remaining Work |
|---|---|---|---|
| CQ-001 | Closed for collection | `tests/test_agent_task_routes.py` now uses `_reset_for_tests()` against `_TaskStore`; full pytest collection reaches execution. | Full suite still has 8 non-collection failures outside the route-test contract. |
| CQ-002 | Closed for active lease overwrite | Focused tests prove an active running lease returns 409 and an expired lease can be reclaimed. | Consider DB-level conditional update if multi-process workers are introduced. |
| CQ-003 | Closed for token exposure | Focused tests prove `?token=` does not authenticate and the rendered admin page does not contain the configured admin token. | Consider adding CSRF protection before exposing mutating admin UI actions beyond the private operator path. |
| CQ-004 | Closed | `/v1/models` and `/v1/embeddings` now use `require_private_api_key` with fail-closed behavior when keys are not configured. | None for this slice. |
| CQ-005 | Closed | `backends.py` has a single `THINKING_BACKENDS` definition including `longcat_web_think`; covered by `tests/test_backend_registry.py`. | None for this slice. |
| CQ-006 | Closed | Retrieval injection consolidated in `context_pipeline/retrieval_injection.py`; duplicate index/preflight lanes removed. | None for this slice. |
| CQ-008 | Closed | Workspace hygiene moved reference clones and local runtime artifacts to `D:\LIMA-external`; `.gitignore` and `docs/WORKSPACE_HYGIENE.md` document boundaries. | Stop-service migration for locked local DBs remains manual. |

## 2026-05-23 Continued Code Review Findings

| ID | Status | Evidence | Remaining Work |
|---|---|---|---|
| CQ-009 | Closed | Full pytest failures after CQ-001 were stale test boundaries around extracted modules and import-time Telegram config. `python -m pytest -q --ignore=active_model` now returns `354 passed, 8 skipped`. | Keep extracted module tests patching the owning module, not `server.py` compatibility aliases. |
| CQ-010 | Closed | `telegram_bot.py` now reads bot token, chat ID, and proxy from environment at call time, so import order no longer breaks tests or runtime reconfiguration. | None for this slice. |
| CQ-011 | Closed | `routes/images.py` had mojibake Chinese detection; it now uses `[\u4e00-\u9fff]` and has a regression test for Chinese prompt quality prefixing. | None for this slice. |
| CQ-012 | Closed | Telegram startup now runs from `server_lifespan.py`; deprecated `@router.on_event("startup")` removed from `routes/telegram.py`. | None for this slice. |
| CQ-013 | Closed | `telegram_notify._fire_and_forget()` now uses a coroutine factory so mocked notification hooks do not leave un-awaited coroutines. | None for this slice. |
| CQ-014 | Closed | Slices 6–9 complete: `smart_router.py` ~228, `http_caller.py` ~390, `health_tracker.py` ~82 lines. | Monitor; optional further http_caller sync/async extraction. |

## 2026-05-24 M0 Baseline Review Harness Follow-Up

| ID | Status | Evidence | Remaining Work |
|---|---|---|---|
| CQ-015 | Closed | `tests/test_device_gateway_routes.py` now uses `monkeypatch` instead of direct `os.environ` mutation, so device-gateway auth setup no longer leaks into MCP tests. | None for this slice. |
| CQ-016 | Closed | `docs/DEVELOPER_CHECKLIST.md` now records the verified green baseline instead of stale routing failures. | None for this slice. |
| CQ-017 | Closed | M1-S1 now centralizes `VISION_BACKENDS`, `STRONG_MODELS`, and `IDE_SOURCES` in `backends.py`; duplicate local tables in `vision_handler.py`, `smart_router.py`, `skills_injector.py`, and `router_v3.py` were removed. | Continue M1-S2 by wiring `key_pool.py` into `http_caller.py`. |
| CQ-018 | Closed | `tests/test_backend_registry.py` now proves routing pools, direct backends, capability lists, GFW backends, weak backends, strong models, and code-capable backends are registered in `BACKENDS`. | None for this slice. |
| CQ-019 | Closed | `http_caller.py` now uses `key_pool.py` when a provider pool is configured, preserves static backend keys when no pool exists, and blocks only when an existing pool is exhausted. | None for this slice. |
| CQ-020 | Closed | `health_tracker.classify_failure()` now normalizes auth, quota, rate-limit, network, malformed, timeout, provider, and manual-refresh failures, and `record_failure()` feeds classified failures into `backend_reputation.py`. | None for this slice. |
| CQ-021 | Closed | `budget_manager.py` now tracks best-effort token telemetry for non-free backends while free/local backends remain non-blocking. | None for this slice. |
| CQ-022 | Closed | M2-S1 moved `http_caller.py` from `urllib.request` to `httpx` while preserving sync API compatibility and adding async call, stream, and raw helpers. Review found and fixed a key-pool status-code regression: internal `BackendError` paths now report the original status code, not a hardcoded 429. | Continue M2 with real concurrent request/cancellation/backpressure tests before adding provider-level concurrency limits. |
| CQ-023 | Closed | `test_http_caller.py` now covers static-key fallback when no env pool is configured, fail-closed behavior when a configured pool is exhausted, empty-stream 502 key-pool reporting, web proxy control-error cleaning, and async success smoke for chat, raw, and stream calls. | Add stress/concurrency tests in the next M2 slice. |
| CQ-024 | Closed | M2-S2 adds `bridge_stream_async()` and async V3 stream adapters so speculative streaming can use native async httpx paths without the legacy thread/queue bridge. Review fixed first-chunk timeout so it uses `asyncio.wait_for()` before waiting indefinitely, and fake-stream async adapters now call `call_api_async()`. | None for this slice. |
| CQ-025 | Closed | M2-S3 replaces the speculative `ThreadPoolExecutor` path with `speculative_call_async()` and keeps `speculative_call()` as a sync compatibility facade. Review fixed the `FIRST_COMPLETED` regression so invalid fast responses do not cancel valid slower responses, preserves latency/failure learning, and makes the sync facade work from an existing event loop. | None for this slice. |
| CQ-026 | Closed | M3 adds LiMa-owned `GraphIndex`, Python stdlib AST extraction, deterministic graph/vector reranking tests, and retrieval metrics without adding LightRAG, GraphRAG, tree-sitter, or hosted reranker runtime dependencies. | Wire these interfaces into the production context pipeline only after M5 eval fixtures can catch retrieval regressions. |
| CQ-027 | Closed | M3 review found AST import resolution was too dependent on callers passing root package keys, and retrieval evaluation skipped queries with missing retrieved rows. Regression tests now cover both cases. | Keep module-map construction explicit when scanning larger repositories. |
| CQ-028 | Open | Free/provider model availability is dynamic. Elephant Alpha exists in OpenRouter metadata but was not routeable during verification because anonymous catalog discovery did not list it and endpoint metadata returned zero endpoints; policy also warns prompts/completions may be logged. | Implement `docs/PROVIDER_MODEL_AUTOMATION_PLAN.md` before adding more provider-driven free backends to hot routing. |
| CQ-029 | Closed | M4 adds typed memory reads, promotion/audit hooks, delete/export controls, and shared redaction for request-time and daemon memory writes. Review fixed the sanitizer rejection path so SSH private keys and promotion evidence cannot fall back to raw storage. | Consider adding a richer typed taxonomy and structured promotion decision objects when memory starts driving autonomous worker policy. |
| CQ-030 | Closed | M5 adds structured quality-gate results, quality-gate tests, and coding eval fixtures. Review fixed mojibake in `routes/quality_gate.py`, made repairable reasons detectable, allowed appropriate safety refusals for harmful prompts, and made `CodingCase.max_chars` plus JSON-list fixture loading real. | Add broader schema assertions and tool-call shape checks when M7 worker/tool contracts land. |
| CQ-031 | Closed | M6 adds local observability events, in-memory metrics, snapshot queries, docs, and hot-path wiring for token usage, quality results, key-pool events, backend success/error, and route decisions. Review fixed event-object redaction and the M6-S3 latency event signature regression so observability cannot break successful `http_caller.call_api()` calls. | None for this slice. |
| CQ-032 | Closed | M7 adds authority classes, executor allowlists, SQLite-backed tool audit, and worker governance registry. Review fixed dangerous-authority fail-closed behavior, made `max_args`/`timeout_sec` effective, redacted audit events before memory/SQLite persistence, and isolated audit/worker DB tests to temp paths. | None for this slice. |
| CQ-033 | Closed | M8 adds a sandbox provider interface, fake temp-dir provider, no-secret fixture, timeout/output/diff/cleanup tests, and no production E2B/CubeSandbox dependency. Review removed shell execution from the fake provider, added upload path normalization, and stopped full host environment leakage into sandbox subprocesses. | Do not connect production workers to any real sandbox provider until explicit tool-gateway approval and network/data policies are wired. |
| CQ-034 | Closed | M9 adds typed streaming/progress events with SSE and OpenAI chunk serialization. Review added non-token event redaction and event-name normalization so tool/error progress events cannot leak key-like values and direct `StreamEvent(event=\"token\")` construction remains serializable. | Wire the protocol into real streaming endpoints only after disconnect/backpressure tests exist. |
| CQ-035 | Closed | M10 adds local data workbench policy, artifact manifests, JSONL storage, retention defaults, schema redaction, and tests. Review fixed import-time manifest path capture, constrained artifact file paths to `LIMA_ARTIFACT_ROOT`, redacted metadata fields, and isolated tests to temp manifest stores. | Keep `last30days-skill` and `MiniMind` out of M10; track them separately as Research Radar and Local Model Lab references. |
| CQ-036 | Closed | M11 adds deployment inventory, CLI status text/JSON output, and a SEARCH/REPLACE edit protocol. Review removed a hardcoded bearer token example, added status-output redaction and unknown-status normalization, made batch edit application strict, and cleaned new sources to ASCII. | Build the fuller ECC-inspired operator shell later from `docs/superpowers/plans/2026-05-24-recent-reference-next-steps.md`; keep current M11 lightweight and non-mutating. |
| CQ-037 | Closed | M12 adds typed motion commands/events and a fake device. Review fixed protocol drift by emitting `command_ack`, reporting `limit_hit` on clamps, requiring homing before pen motion, making stop raise the pen, validating path feed/point count, and cleaning new files to ASCII. | Keep real hardware transport gated behind explicit auth, private network policy, and dry-run/fake-device smoke tests. |
| CQ-038 | Closed | M13-S1 adds provider catalog entries, snapshots, deltas, admission/probe state, serialization, and tests. Review fixed cross-provider delta confusion, added routeability defaults and redaction, stabilized added/removed ordering, and made capability ordering non-semantic. | Do not stage untested `openrouter.py`, `probe.py`, or `report.py` with S1 unless their follow-up slices and tests are completed. |
| CQ-039 | Closed | M13-S2 through S5 complete Provider Model Automation with OpenRouter parsing, safe probe harness, redacted change reports, and patch-plan-only admission. Review fixed runtime live-fetch gating, endpoint-count defaulting, metadata probe permissiveness, probe self-promotion, and report/admission redaction. Focused provider tests return 30 passed and the full suite returns 828 passed, 8 skipped. | Keep provider automation default-off for live network fetches. Human review remains required before any model becomes `routing_enabled`; patch plans must not auto-edit `backends.py`. |
| CQ-040 | Closed | M14 adds provider snapshot storage, batch probe runner, review bundle generation, and routing impact smoke analysis. Review fixed snapshot path sanitization, same-second overwrite risk, reset-all cleanup, silent probe downgrade when requested callables are missing, probe-level ordering, markdown redaction, pool-only removal warnings, and ASCII cleanup. Focused provider tests return 56 passed and the full suite returns 854 passed, 8 skipped. | Keep the M14 loop operational-only until a human-approved workflow exists for applying patch plans. Snapshot/report outputs are safe to review, but generated plans still must not auto-edit `backends.py`. |
| CQ-041 | Closed | M15 adds Research Radar source records, catalog search/filter/counts, and seeded reference metadata. Review fixed required-field validation, source record round-trip parsing, secret redaction, duplicate source-id overwrite risk, case-insensitive tag filtering, deterministic search ties, copy-restricted license policy, and incorrect seed metadata for Shadowbroker/last30days/LEANN. Focused research tests return 25 passed and the full suite returns 879 passed, 8 skipped. | Treat Research Radar as provenance and planning data only. AGPL/GPL/source-available/unknown sources remain concept/reference only unless a later explicit license review approves code adoption. |
| CQ-042 | Closed | M16 adds local retrieval manifests, chunking, a toy in-memory token index, an eval bridge to M3 retrieval metrics, and a LEANN boundary. Review fixed manifest chunk round-tripping, secret-like metadata key redaction, chunk source metadata, empty path/snippet bugs in search hits, deterministic empty/top_k search behavior, hit output redaction, eval tests that now assert real recall/MRR, and ASCII cleanup. Focused local retrieval tests return 27 passed and the full suite returns 906 passed, 8 skipped. | Keep LEANN as an optional boundary only. Do not add heavy retrieval dependencies or store full document text in manifests unless a later explicit adapter/eval decision approves it. |
| CQ-043 | Closed | M17 adds agent runtime contracts, deterministic planning, dry-run execution, lifecycle events, and tool policy boundaries. Review fixed missing contract round-trips, command/metadata/audit redaction, runtime policy bypass, shell/HTTP fail-closed behavior, event fallback redaction, audit-log sanitization, non-mutating policy filtering, and ASCII cleanup. Focused agent runtime tests return 33 passed and the full suite returns 939 passed, 8 skipped. | Keep the runtime dry-run and proposal-only until an explicit approval workflow wires real tools, shell execution, network calls, or workspace writes through the M7 tool gateway and audit path. |
| CQ-044 | Closed | M18 adds agent runtime persistence and resume support. Review fixed stale JSONL reads, deduped latest task listing, final task-status persistence, sanitized in-memory/JSONL storage, blocked-result queries, completed-task resume semantics, resume-state redaction, and ASCII cleanup. Focused agent store/runtime tests return 65 passed and the full suite returns 971 passed, 8 skipped. | Keep persisted runs sanitized and local-only. Do not use stored state to auto-resume shell, network, workspace-write, deployment, or hardware actions until explicit approval and tool-gateway audit paths are wired. |
| CQ-045 | Closed | M19 adds a local agent run orchestrator with requests, leases, queue status, submit/list/claim/finish/retry/run-one, lease expiry, stats, recovery, and safe event bridging. Review fixed stale store recovery after finish, mismatched-result finishing, late terminal overwrites, direct run-one lease bypass, expired-claim reclaim, blocked-result task status, recovery of terminal/blocked results, event-sink failure isolation, exports, and ASCII cleanup. Focused agent orchestrator/store/runtime tests return 91 passed and the full suite returns 997 passed, 8 skipped. | Keep orchestration local and dry-run-first. Do not add multi-process claims, durable queue state, automatic retries, shell/network/workspace execution, or worker fan-out until explicit approval and tool-gateway audit wiring exist. |
| CQ-046 | Closed | M20 adds durable JSONL state for orchestrator requests and leases. Review fixed atomic state writes, filename-only state paths, state-field redaction, actual restored-count semantics, missing-file store recovery, bad-record tolerance, unknown-status/default parsing, claimed-without-lease recovery, valid-lease duplicate-claim blocking after restart, idempotent load counts, and ASCII cleanup. Focused orchestrator tests return 39 passed, focused agent orchestrator/store/runtime tests return 104 passed, and the full suite returns 1010 passed, 8 skipped. | Keep queue state local and sanitized. Do not treat JSONL state as a multi-process durable queue or source of permission to auto-run shell/network/workspace-write actions; those still require explicit tool-gateway approval and audit wiring. |
| CQ-047 | Closed | M21 adds worker heartbeat governance on top of the local orchestrator queue. Review fixed package exports, busy-worker double-claim prevention, quarantine persistence across re-register, offline/quarantined mark-idle protection, worker lease release behavior, import placement, and ASCII cleanup. Focused orchestrator tests return 54 passed, focused agent orchestrator/store/runtime tests return 119 passed, and the full suite returns 1025 passed, 8 skipped. | Keep worker governance local and advisory. Do not use heartbeat or lease ownership as permission to execute shell/network/workspace-write/deployment/hardware actions until tool-gateway approval and audit paths are explicitly wired. |
| CQ-048 | Closed | M22 adds a dry-run-first approval gate for real tool execution requests. Review fixed package exports, approval request redaction, exact approval matching by step/task/worker/kind/command, duplicate pending/denied/expired request generation, expired approved-request handling, denied/approved immutability, audit sink failure isolation, and ASCII cleanup. Focused approval tests return 23 passed, focused approval/orchestrator/runtime tests return 110 passed, and the full suite returns 1048 passed, 8 skipped. | Keep the approval gate decision-only until it is wired into AgentRuntime and M7 tool gateway execution. Approval alone must not execute shell/network/workspace-write/deployment/hardware actions. |
| CQ-049 | Closed | M23 wires the approval gate into `AgentRuntime.run_step()` before tool policy and handlers. Review fixed missing task/worker approval context by adding `run_step(..., task_id, worker_id)`, passing task ids from `run()`, preventing approval reuse across task ids, preserving tool policy/runtime blocking after approval, import placement, and ASCII cleanup. Focused agent store tests return 39 passed, focused store/approval/runtime tests return 95 passed, and the full suite returns 1055 passed, 8 skipped. | Keep runtime approval as a gate only. Do not add real shell/network/workspace-write execution until M7 tool gateway execution boundaries, audit persistence, and operator approvals are wired together. |
| CQ-050 | Closed | M24-M27 add safe tool-execution boundary types, JSONL audit persistence, operator CLI helpers, and an E2E release gate. Review fixed secret redaction in executor output and audit records, fake-executor response leakage across instances, global audit path pinning, package exports, CLI approval-output redaction, test audit-path isolation, and ASCII cleanup. Focused E2E release tests return 29 passed, focused agent runtime/orchestrator/store/approval/E2E tests return 178 passed, and the full suite returns 1084 passed, 8 skipped. | These milestones still provide boundaries, audit, and operator controls only. Keep real shell/network/workspace-write/deployment/hardware execution disabled until a later tool gateway binds approvals, allowlists, audit persistence, and explicit operator intent into one reviewed execution path. |
| CQ-051 | Closed | M28-M33 wire the tool gateway into runtime, add operator approval sessions, feature flags, workspace sandboxing, network policy, and release hardening tests. Review fixed mojibake, stable gateway audit event names, missing task/worker context on blocked audit paths, run-tests gateway routing, dangerous allowed-tools policy after approval, no-op/fake blocked semantics, approval-session redaction, dry-run-aware env allowlists, workspace path escape checks, exact/subdomain network matching, package exports, and overbroad `sk-` redaction that hid normal ids like `task-1`. Focused M28-M33 tests return 45 passed, focused agent/runtime/operator tests return 223 passed, and the full suite returns 1129 passed, 8 skipped. | Real execution remains gated off. Do not add a real shell/network/workspace executor until there is an operator-reviewed execution session that binds approval, feature flags, allowlists, sandbox/network policies, and audit evidence into one replayable decision record. |
| CQ-052 | Closed | M34 adds a real-executor scaffold with multi-gate preflight and a disabled executor. Review fixed mojibake, typed step construction, workspace preflight using the requested path instead of an empty string, network/workspace all-gates-passed disabled coverage, audit sink exception isolation, redacted command previews, and package exports. Focused real-executor tests return 18 passed, focused execution-gate tests return 92 passed, and the full suite returns 1147 passed, 8 skipped. | This is still a disabled scaffold. Real shell/network/workspace execution remains prohibited until an explicit, documented release decision replaces the disabled executor with reviewed implementations and replayable operator evidence. |
| CQ-053 | Closed | PROD-008 commit `b372ccc` adds a learning loop that feeds task-result evidence into memory, prompt profiles, routing feedback, and eval candidates without directly changing routing pools. Review verified the evidence-only gate and reran focused plus full tests. | Keep `reference_pattern` promotion as evidence only. Any behavior-changing prompt or route adoption still needs an explicit eval/release gate. |
| CQ-054 | Closed | V1 WeChat guest safety adds guest/owner binding roles, guest-safe command handlers, sidecar routes, smoke tools, and route mounting in `server.py`. Review fixed owner-only dispatch for real owner bindings and hardened sidecar auth to require `Bearer` with constant-time token comparison. Focused tests return 106 passed, guest smoke returns 14/14 steps, and the full suite returns 1346 passed, 8 skipped. | Owner command handlers remain V1 stubs. Do not connect `/code-task`, `/device`, `/artifact`, `/memory`, or `/status` to real private actions until a separate reviewed owner-auth and audit slice lands. |
| CQ-055 | Closed | P1.1/P1.2/P1.3 adds cross-system correlation, explicit eval approval gates, and the LiMa Code `/lima fix` workflow. Review fixed the documented `/v1/ops/correlate?id=...` query shape and made eval approvals visible in `revision_check()` without auto-mutating routing. Focused P1 tests return 59 passed and the full suite returns 1348 passed, 8 skipped. VPS deployment of `645a6fc` passed remote compile, service restart/health, authenticated local ops smoke, public ops smoke, and public online smoke `12/12 checks passed`; backup is `/opt/lima-router/backups/p1-review-20260525_113033/runtime-before.tgz`. | Keep eval approval as evidence/audit only until a separate release gate applies any route or prompt behavior change. No real-device validation was run because no hardware is currently available. |
| CQ-057 | Closed | Quality-fix review closed ops metrics `recent_agent_tasks`, admin CSRF/XSS hardening, strict Bearer auth, eval promotion abort-on-write-failure, and channel draw/device integration fixes. Focused tests return 48 passed; full suite returns 1366 passed, 10 skipped. VPS deploy at `62ad977` with backup `/opt/lima-router/backups/quality-fix-20260525_133000/runtime-before.tgz`; public smoke `12/12` with exact `quality_fix_62ad977_ok`. | Keep `/v1/ops/eval/apply` behind private auth and human release review. Bearer-only auth is now required for private API paths. |
| CQ-058 | Closed | Code-quality follow-up closes `/v1/models` and `/v1/embeddings` auth fail-open gaps, makes Telegram webhook fail-closed when bot is configured, wires `route_scorer` into `code_orchestrator` and `routes/tool_forward`, and adds logging for orchestrator backend failures. VPS smoke verified Bearer `/v1/models` and public `12/12`. | None for this slice. |
| CQ-059 | Closed | CQ-006 retrieval duplication removed by moving graph/vector/rerank injection into `context_pipeline/retrieval_injection.py` as the single authority. `routing_engine.route()`, `request_context_preflight.maybe_enhance_messages()`, and `code_context_processor()` now delegate to that module; legacy index singleton path deleted. VPS retrieval trace smoke hit `routing_engine.py` with 192 injected chars. | Keep MCP `search_repo` on the same retrieval primitives; do not reintroduce a second message-mutation path. |
| CQ-060 | Closed | CQ-014 slice extracts post-route integrations to `route_post_process.py`; replaces silent broad catches in `routing_engine` post-route path and `http_caller` prefix-cache optimization with warning logs. Documented pipeline authority in `docs/REQUEST_PIPELINE_AUTHORITY.md`. | Continue CQ-014 on `smart_router.py`, `server.py`, and remaining oversized modules. |
| CQ-061 | Closed | CQ-014 slice 2 extracts admin dashboard HTML/JS to `routes/admin_ui.py`. Slice 11 further splits API/backends/state; `routes/admin.py` ~68 lines. | None. |
| CQ-062 | Closed | CQ-014 slice 3 centralizes router registration in `routes/route_registry.py`; `server.py` re-exports handler aliases. Tests in `tests/test_route_registry.py`. | Extract `_handle_chat` / streaming from `server.py` in a follow-up slice. |
| CQ-063 | Closed | CQ-022/023 follow-up adds async parallel and threaded burst tests in `tests/test_http_caller_concurrency.py` (mocked httpx, no live stress harness). | Add provider-level concurrency limits and optional live soak harness later. |
| CQ-064 | Closed | CQ-014 slice 4 moves `_handle_chat` / streaming to `routes/chat_handler.py`, `routes/chat_stream.py`, `routes/chat_support.py`; `server.py` reduced to ~180 lines. Tests updated in `tests/test_chat_handler.py`. | Optional: trim `chat_handler` orchestration block further. |
| CQ-065 | Closed | CQ-014 slice 5 extracts non-stream quality fallback to `routes/chat_fallback.py`; `chat_handler.py` ~315 lines. Tests in `tests/test_chat_fallback.py`. | None for this slice. |
| CQ-066 | Closed | CQ-014 slice 6 extracts `router_circuit_breaker.py`, `router_intent.py`, `router_classifier.py` from `smart_router.py`; re-exports preserve API. Tests: `tests/test_router_circuit_breaker.py`, `tests/test_router_classifier.py`. | Continue HTTP/vision extraction from `smart_router.py`. |
| CQ-067 | Closed | RAG offline eval fixture: `tests/fixtures/retrieval_eval/lima_core.json`, `context_pipeline/retrieval_eval_runner.py`, gate thresholds (hit_rate/recall/MRR). Tests: `tests/test_retrieval_eval_fixture.py`. | Add production-corpus fixtures; optional graph_relations in fixture schema. |
| CQ-068 | Closed | CQ-014 slice 7 extracts `router_prompt.py`, `router_http.py`, `router_image.py`; vision helpers deduped to `vision_handler.py`; `clean_response` unified via `response_cleaner.py`. `smart_router.py` ~228 lines. VPS smoke `cq014_http_caller_ok` 12/12 (deployed with slice 8). | None for slice 7. |
| CQ-069 | Closed | CQ-014 slice 8 splits `http_caller.py` into `http_errors.py`, `http_request_builder.py`, `http_response.py`, `http_stream.py`; re-exports preserve test patch points. VPS smoke `cq014_http_caller_ok` 12/12. | Optional: extract sync/async call bodies to dedicated modules. |
| CQ-070 | Closed | CQ-014 slice 9 splits `health_tracker.py` into classifier/state/recorder/scoring modules; `health_tracker.py` ~82 lines. VPS smoke `cq014_health_tracker_ok` 12/12. | None for CQ-014 file-size track. |
| CQ-071 | Closed | RAG fixture extended: `lima_routing.json`, `routing_corpus/`, `dual_layer` eval in `retrieval_eval_runner.py`. Tests +2. | Production corpus indexing when retrieval wired to repo scan. |
| CQ-072 | Closed | HTTP slice 10: `http_sync.py`/`http_async.py`; `http_caller.py` ~38 lines. Chat slice 10: preflight/post-closeout; `chat_handler.py` ~253 lines. VPS smoke `cq014_rag_http_chat_ok` 12/12. | None. |
| CQ-073 | Closed | CQ-014 slice 11: admin split, routing_engine split, prod RAG fixture. Tests **1432 passed**. VPS deploy + smoke 7/7. | None. |
| CQ-074 | Closed | Identity hardening: guard-before-cache, As-Claude patterns, stream sanitizer, guest channel role. Tests **1446 passed**. Commit `77d8d8c`. | None. |
| CQ-075 | Closed | RAG CI gate: `run_all_fixture_gates()`, `lima-ci.yml`, `rag_gate` marker. Tests **1451 passed**. | Monitor CI on push. |
| CQ-076 | Closed | Prod retrieval wired + VPS deploy/smoke. Trace hit `routing_engine.py`/`health_tracker.py`, 380 injected chars. Token `prod_retrieval_trace_ok`. | None. |
| CQ-077 | Closed | Deploy manifest expanded (routing split + retrieval stack); `response_cleaner` SyntaxWarning fix; `test_agent_eval` portable path. VPS redeploy smoke **prod_retrieval_trace_ok** (380 chars). | None. |
| CQ-078 | Closed | Admin portable paths: `FALLBACK_LOG` shares `request_tracking` resolver; `admin_retrain` uses repo root cwd. Tests in `tests/test_admin_paths.py`. | None. |
| CQ-079 | Closed | CTX-003 tool-route preflight: Tier-2 Anthropic body + `tool_call_forward` aligned with OpenAI tier-1 injection. VPS smoke **ctx003_messages_ok** (`stop_reason=tool_use`, preflight 340 chars). Tests **1460 passed**. | None. |
| CQ-080 | Closed | Review fixes: ASGI body cap + JSON Content-Length policy (`http_body_limit.py`); Tier1 sync `record_failure`; Anthropic `tool_result`+text conversion preserved. Tests **1466 passed**. | None. |
| CQ-081 | Closed | CQ-014 slice 12 P3 splits: `chat_handler_dispatch`, `anthropic_messages_handler`, `anthropic_vision_sse`, `tool_forward_stream`; hot-path functions under ~65 lines. Tests **1466 passed**. | None. |
| CQ-082 | Closed | Repo hygiene: `test_repo_hygiene.py`, `scripts/archive/`, deepcode-cli `data/` ignore, untrack unused `router_ml_model.pkl`, `scripts/README.md`. | VPS `backups/` grows fast; prune before deploy when disk full. |
| CQ-083 | Closed | VPS bundle deploy `deploy_vps_bundle.py`: CQ-080 security + CQ-081 P3 splits + retrieval. Smokes `prod_retrieval_trace_ok`, `ctx003_messages_ok`. Tests **1470 passed**. | None. |
| CQ-084 | Closed | VPS `backups/` wiped (~11G freed); deploy scripts no longer create tar backups; `cleanup_vps_backups.py` for ops. Rollback via GitHub only. | None. |
| CQ-085 | Closed | CODE_QUALITY plan P0/P1: ASGI body buffer cap, `/api/live-key` metadata-only, `key_rotation` retired to archive, semantic cache write observability, admin constant-time login. Tests **1477 passed**. | Gemini Live needs server-side proxy; VPS smoke after deploy recommended. |
| CQ-086 | Closed | P1.3 silent-catch logging; `quality_gate` split (235+79+69 lines); `CLAUDE.md` trimmed + `repo_stats.py`; `tests/README.md`. Tests **1477 passed**. | Next splits: `agent_tasks`, `orchestrator`, `store`, `backends`; P2.2 pipeline authority doc. |
| CQ-087 | Closed | Split `agent_tasks`, `orchestrator`, `session_memory/store`, `backends`; REF-005 pipeline authority doc expanded. Tests **1481 passed**. | `orchestrator_queue` (308) and `agent_tasks` routes (316) still slightly over 300-line target. |
| REF-006 | Closed | GCP `generative-ai` repo assessed in `docs/GCP_GENERATIVE_AI_RESEARCH.md`: reference-only (eval/RAG methodology), no deep port; llmevalkit/agents are GCP-locked demos. Local RAG eval fixture delivered (CQ-067). | Add LiMa routing corpus fixture when retrieval wired to production path. |
