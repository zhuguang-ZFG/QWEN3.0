# JDCloud Workspace Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat the new JDCloud server as a real LiMa ops node while removing local credential/scratch noise from day-to-day repository status.

**Architecture:** Keep durable, non-secret JDCloud facts in tracked docs and tracked deploy templates. Keep password-bearing one-off scripts, generated deployment notes, and local diagnostic files out of Git with exact ignore rules. Do not delete operator files in this slice; only remove tracked local runtime state from the index when the file is clearly machine-local.

**Tech Stack:** Git hygiene, markdown ops docs, `.gitignore`, existing `deploy/jdcloud/` shell/systemd assets.

---

## File Structure

- Modify: `.gitignore` for exact local JDCloud scratch and credential-bearing files.
- Modify: `.codegraph/.gitignore` and remove `.codegraph/daemon.pid` from the Git index while preserving the local file.
- Modify: tracked JDCloud deploy assets already changed for the live server's `python3`/`pip3` environment:
  - `deploy/jdcloud/deploy_probe_platform.sh`
  - `deploy/jdcloud/install_playwright.sh`
  - `deploy/jdcloud/lima-probe-browser.service`
  - `deploy/jdcloud/lima-probe.service`
- Create: `deploy/jdcloud/README.md` as the active manifest for tracked JDCloud assets.
- Create: `docs/ops/JDCLOUD_RUNTIME_STATUS.md` as the sanitized runtime status and credential boundary.
- Update: `docs/ONLINE_DISTRIBUTIONS.md`, `docs/DOCUMENTATION_STATUS.md`, `STATUS.md`, `progress.md`, and `findings.md` with the hygiene closeout.

## Tasks

### Task 1: Protect Local JDCloud Scratch

**Files:**
- Modify: `.gitignore`
- Modify: `.codegraph/.gitignore`
- Remove from index only: `.codegraph/daemon.pid`

- [x] Add exact ignore entries for local JDCloud password helpers, generated reports, and root scratch scripts.
- [x] Ignore CodeGraph PID files and remove `.codegraph/daemon.pid` from the index without deleting the local file.
- [x] Verify `git status --short` no longer shows the protected scratch files.

### Task 2: Document JDCloud As An Ops Node

**Files:**
- Create: `deploy/jdcloud/README.md`
- Create: `docs/ops/JDCLOUD_RUNTIME_STATUS.md`
- Modify: `docs/ONLINE_DISTRIBUTIONS.md`
- Modify: `docs/DOCUMENTATION_STATUS.md`

- [x] Record JDCloud role as a secondary provider-probe/monitoring node, not the primary LiMa router.
- [x] Record tracked assets and local-only secret-bearing files.
- [x] Record that credentials must come from SSH keys, env vars, or an operator secure channel, never committed scripts.
- [x] Record that LiMa production API traffic still uses `chat.donglicao.com/v1`.

### Task 3: Validate And Close Out

**Files:**
- Modify: `STATUS.md`
- Modify: `progress.md`
- Modify: `findings.md`

- [x] Run focused checks for docs/ignore hygiene.
- [x] Run `git diff --check` and staged secret scan.
- [x] Stage only JDCloud hygiene files.
- [x] Commit and push GitHub `origin`; record that this checkout still has no Gitee remote if unchanged.
