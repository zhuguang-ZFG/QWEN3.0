# LiMa Developer Checklist

> Purpose: one doc to know how to submit a slice for review.
> Each command should pass before opening a review.

## How To Submit A Slice For Review

1. Read `docs/REVIEW_PACKET_TEMPLATE.md`.
2. Fill in all sections of the review packet.
3. Run the relevant test commands from this checklist.
4. Paste command output into the review packet.
5. Open the review with Codex.

## Test Commands By Area

### Router / Core

```powershell
python -m pytest test_routing_engine.py test_http_caller.py test_streaming.py -q --ignore=active_model
```

### Backend Registry / Key Pool

```powershell
python -m pytest tests/test_backend_registry.py tests/test_key_pool.py -q --ignore=active_model
```

### Context Pipeline / Code Context

```powershell
python -m pytest tests/test_context_pipeline.py tests/test_code_context_index.py tests/test_lima_context.py -q --ignore=active_model
```

### Memory

```powershell
python -m pytest tests/test_session_memory.py tests/test_compactor.py tests/test_typed_memory.py tests/test_prompt_memory_recall.py -q --ignore=active_model
```

### Eval / Quality Gate / Coding

```powershell
python -m pytest tests/test_coding_eval.py test_code_orchestrator.py -q --ignore=active_model
```

### Agent Tasks / Worker Contract

```powershell
python -m pytest tests/test_agent_task_routes.py tests/test_agent_task_contract.py tests/test_admin_agent_audit.py -q --ignore=active_model
```

### Device Gateway

```powershell
python -m pytest tests/test_device_gateway_protocol.py tests/test_device_gateway_routes.py tests/test_device_gateway_store.py tests/test_device_gateway_concurrency.py -q --ignore=active_model
```

Redis HA store slice:

```powershell
python -m pytest tests/test_device_gateway_redis_store.py tests/test_device_gateway_routes.py -q --ignore=active_model
```

### Streaming

```powershell
python -m pytest test_streaming.py tests/test_stream_footer.py -q --ignore=active_model
```

### Mastery / Evolution

```powershell
python -m pytest tests/test_mastery_loop.py tests/test_agent_evolution.py -q --ignore=active_model
```

### Access Guard / Security

```powershell
python -m pytest tests/test_access_guard.py tests/test_secret_hygiene.py tests/test_zerokey_endpoints.py -q --ignore=active_model
```

### Tool Gateway / MCP

```powershell
python -m pytest tests/test_tool_gateway.py tests/test_mcp_tools.py tests/test_lima_code_dev_search_tools.py -q --ignore=active_model
```

### Full Suite

```powershell
python -m pytest -q --ignore=active_model
```

## Pre-Commit Checks

```powershell
python -m py_compile <changed_files>
git diff --check
git status --short --branch
```

## Known Baseline (2026-05-25)

- Branch: `codex/free-web-ai-probe`
- `python -m pytest test_routing_engine.py -q --ignore=active_model`: 43 passed.
- `python -m pytest -q --ignore=active_model`: 476 passed, 8 skipped.
- Device Gateway focused suite after Redis HA: `31 passed`.
- Agent-task plus Device Gateway smoke subset after Redis HA: `45 passed`.
- Online distribution smoke after Redis HA and public `6379` guard: `12/12`.
- No known failing tests in the current baseline.

## Out-Of-Scope Untracked Files

These files exist in the working tree but are not part of this implementation plan.
Do not stage or commit them:

- `.claude/`, `.playwright-mcp/`
- `debug_routing*.py`, `run_*_test.py`, `deploy_*_test.py`, `stress3_runner.py`
- `aider-context-construction.md`, `claude-code-context-construction.md`, `cline-context-construction.md`, `codex-context-construction.md`, `continue-context-construction.md`, `cursor-context-construction.md`, `gemini-cli-context-construction.md`
- `ERROR_FINGERPRINTS.md`, `xue_routing_design.md`
- `auth.py`, `commercial_config.py`, `quota_ledger.py`, `usage_store.py`, `r13_remote.py`
- `_voice_call.html`, `_voice_gateway.py`, `lima-demo-fixed.js`, `monitor_dashboard.html`
- `requirements.txt`
- `deploy_to_ollama.bat`, `setup_and_train.bat`, `start_tunnel.bat`
- `inkscape-master.zip`, `rtk_latest.zip`
- Chinese-named files and directories
