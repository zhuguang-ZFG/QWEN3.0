# Public Proxy Secret Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the in-progress public proxy routes without committing live API keys or silent failure paths.

**Architecture:** Leave the existing dirty feature files in place, but replace committed secrets with environment variables or deployment placeholders. API routes fail explicitly with 503 when required provider keys are absent and log JSON parse failures instead of silently raising generic errors.

**Tech Stack:** Python 3.10, FastAPI, httpx, nginx config snapshots, ruff, pytest.

---

### Task 1: Remove Live Credentials From Dirty Proxy Work

**Files:**
- Modify: `routes/agnes_proxy.py`
- Modify: `routes/jina_embedding.py`
- Modify: `routes/st236600_proxy.py`
- Modify: `deploy/nginx/www.donglicao.com.conf`
- Modify: `infra/vps/nginx/www.donglicao.com.conf`
- Modify: `deploy/nginx/chat.donglicao.com.conf`

- [x] **Step 1: Move provider keys to environment variables**

`AGNES_API_KEY` and `JINA_API_KEY` are read from the environment. Missing values return HTTP 503.

- [x] **Step 2: Replace nginx Authorization values with placeholders**

Repository nginx snapshots use `REPLACE_WITH_LIMA_API_KEY`; deploy code must inject the real key from the VPS secret store.

- [x] **Step 3: Replace silent JSON parse failures**

Invalid request JSON now logs the exception type before returning HTTP 400.

- [ ] **Step 4: Verify**

Run:

```text
.\.venv310\Scripts\python.exe -m ruff check routes\agnes_proxy.py routes\jina_embedding.py routes\st236600_proxy.py routes\route_registry.py
.\.venv310\Scripts\python.exe -m pytest tests\test_chat_endpoints.py tests\test_responses_endpoints.py -q
git diff | rg -n "Bearer [A-Za-z0-9._-]{20,}|sk-[A-Za-z0-9]|jina_[A-Za-z0-9-]+"
```
