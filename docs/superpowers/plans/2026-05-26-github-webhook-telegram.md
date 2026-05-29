# GitHub Webhook → Telegram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:test-driven-development for each task.

**Goal:** Receive GitHub webhooks on LiMa Server and push concise event summaries to Telegram.

**Architecture:** Small `github_webhook/` package (verify + format) + thin `routes/github_webhook.py` route; reuse `telegram_notify` fire-and-forget pattern. Default-off via env.

**Tech Stack:** FastAPI, HMAC-SHA256, pytest, existing telegram_bot stack.

---

### Task 1: Event formatter (pure functions)

**Files:**
- Create: `github_webhook/format.py`
- Test: `tests/test_github_webhook.py`

- [ ] Write failing tests for push / pull_request / workflow_run formatting
- [ ] Implement `format_github_event(payload) -> str | None`
- [ ] Run focused tests → PASS

### Task 2: Signature verification

**Files:**
- Create: `github_webhook/verify.py`

- [ ] Write failing tests for valid/invalid/missing signature
- [ ] Implement `verify_github_signature(body, header, secret) -> bool`
- [ ] Run focused tests → PASS

### Task 3: HTTP route + notify hook

**Files:**
- Create: `routes/github_webhook.py`
- Modify: `telegram_notify.py`, `routes/route_registry.py`

- [ ] Write failing endpoint tests (403 bad sig, 503 disabled, 200 push)
- [ ] Implement route + `notify_github_event`
- [ ] Register router in route_registry
- [ ] Run focused tests → PASS

### Task 4: Closeout

- [ ] Full suite `pytest -q --ignore=active_model`
- [ ] Update `progress.md` / design doc status
