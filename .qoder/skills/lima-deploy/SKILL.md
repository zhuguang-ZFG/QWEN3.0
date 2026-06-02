---
name: lima-deploy
description: Automated VPS deployment and verification for the LiMa backend. Covers deploy scripts, SSH connection, backup, upload, restart, /health check, public HTTPS smoke testing, rollback, and evidence collection. Use when deploying code to VPS, running smoke tests, diagnosing deployment failures, or verifying production health.
---

# LiMa VPS Deployment & Verification

## Quick Reference

| Item | Value |
|------|-------|
| VPS | 47.112.162.80 (chat.donglicao.com) |
| SSH user | root |
| SSH key | `~/.ssh/id_ed25519` |
| Service | `lima-router.service` (systemd, port 8080) |
| Remote dir | `/opt/lima-router` |
| Python | Python 3.10 on VPS |
| Health endpoint | `http://127.0.0.1:8080/health` |

## Standard Deploy Flow (Auto-Closeout)

```
1. Local gate: pytest + ruff check
2. Deploy: scripts/deploy_v3.py or scp individual files
3. Restart: systemctl restart lima-router
4. Health: curl http://127.0.0.1:8080/health
5. Smoke: run slice-specific smoke test
6. Evidence: update progress.md / findings.md
7. Git: add milestone files only → commit → push origin
```

## Deploy Methods

### Method A: deploy_v3.py (Full Bundle)

```bash
# Requires LIMA_DEPLOY_KEY_PATH or LIMA_DEPLOY_PASS
$LIMA_DEPLOY_KEY_PATH = "~/.ssh/id_ed25519"
python deploy_v3.py
```

Uploads all core files + module directories in one shot. Creates backup with timestamp.

### Method B: Individual File SCP (Targeted Fix)

```bash
scp -i ~/.ssh/id_ed25519 <local_file> root@47.112.162.80:/opt/lima-router/<remote_path>
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 "systemctl restart lima-router"
```

Use when: hotfix for a single file, avoid full bundle upload.

### Method C: scripts/deploy_unified.py (Newer Bundles)

Check `scripts/deploy_*.py` for slice-specific deploy scripts. Each has its own file list.

## SSH Commands

```bash
# Health check
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 "curl -s http://127.0.0.1:8080/health"

# Service status
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 "systemctl is-active lima-router"

# Port check
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 "ss -tlnp | grep 8080"

# Recent logs (last 20 lines, filter Telegram noise)
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 "journalctl -u lima-router --no-pager -n 20 --output=cat | grep -v Telegram"

# Full error trace
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 "journalctl -u lima-router --no-pager --since '5 min ago' --output=cat | grep -iE 'error|traceback|exception' | grep -v Telegram"
```

## Smoke Testing

### Generic OpenAI Protocol Smoke

```python
import httpx, json

resp = httpx.post(
    "https://chat.donglicao.com/v1/chat/completions",
    headers={"Authorization": "Bearer <API_KEY>", "Content-Type": "application/json"},
    json={
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 50,
    },
    timeout=30,
)
print(resp.status_code, resp.text[:200])
```

### Anthropic Protocol Smoke

```python
resp = httpx.post(
    "https://chat.donglicao.com/v1/messages",
    headers={
        "x-api-key": "<API_KEY>",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    },
    json={
        "model": "claude-3-haiku-20240307",
        "max_tokens": 50,
        "messages": [{"role": "user", "content": "hello"}],
    },
    timeout=30,
)
```

### Tool Call Smoke (Both Protocols)

Upload `_smoke_tool.py` to VPS and run:

```bash
scp -i ~/.ssh/id_ed25519 _smoke_tool.py root@47.112.162.80:/tmp/smoke_tool.py
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 "python3.10 /tmp/smoke_tool.py"
```

## Rollback

```bash
# Find latest backup
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 "ls -lt /opt/lima-router/server.py.bak.* | head -3"

# Rollback
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 \
  "cp /opt/lima-router/server.py.bak.<TIMESTAMP> /opt/lima-router/server.py && systemctl restart lima-router"
```

## Common Failure Patterns

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 500 on /v1/chat/completions | Python exception in request path | Check `journalctl -u lima-router` for traceback |
| Health returns empty | Server still starting | Wait 10s, check `ss -tlnp \| grep 8080` |
| `UnboundLocalError` | Local import shadows module-level import | Remove the local import inside function |
| Port not listening | Startup crash or port conflict | Check logs, verify `.env` is intact |
| Service `failed` (signal 9) | OOM or manual kill | Check `dmesg` for OOM, restart |
| `JSONDecodeError` from curl | PowerShell quote escaping issue | Use Python script instead of SSH+curl |

## .env Safety Rules

- **Never overwrite** VPS `.env` during deploy
- Use `cat >> .env` to append new variables
- Always backup `.env` before any deploy operation
- If service breaks after deploy, check `.env` first

## Evidence Checklist

Before claiming "deployed":

- [ ] Local pytest passed
- [ ] `git status` reviewed (no unintended files)
- [ ] Backup created and rollback command recorded
- [ ] `/health` returns `{"status":"ok"}`
- [ ] Smoke test(s) passed with actual response
- [ ] `progress.md` and `findings.md` updated with evidence
