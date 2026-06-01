> ⚠️ 2026-06-01 起已过时。FRP 已停用。当前状态见 STATUS.md

# LiMa Ops Entrypoints

> Superseded and expanded by `docs/ONLINE_DISTRIBUTIONS.md`.

## Purpose

This file preserves the original FreeDomain-inspired plan target name. The
active source of truth for VPS-hosted public surfaces is now
`docs/ONLINE_DISTRIBUTIONS.md`, which covers the official website, open
platform, chat interface, FRP endpoint, nginx edge, and service snapshots.

## Current Entrypoints

| Name | URL | Owner | Health | Auth |
|---|---|---|---|---|
| Official website | `https://www.donglicao.com` | lima | `/` | public |
| Primary chat/API | `https://chat.donglicao.com` | lima | `/health` | private key for API calls |
| Open platform | `https://api.donglicao.com` | lima | `/` | New API token |
| FRP validation | `http://47.112.162.80:8088` | lima | `/health` | private key for API calls |

## Rules

- Public API traffic should prefer HTTPS through nginx.
- Internal service ports such as `8080`, `3003`, and `8091` must not be
  directly reachable from the public internet.
- `/health` and `/v1/models` may remain public for uptime and IDE discovery.
- `/v1/chat/completions`, `/v1/messages`, agent routes, live-key/status, and
  image generation require private access.
- Record DNS, FRP, VPS, nginx, systemd, certificate, and public surface changes
  in `docs/ONLINE_DISTRIBUTIONS.md`, `infra/vps/`, `STATUS.md`,
  `docs/LIMA_MEMORY.md`, and `progress.md`.
- Do not store provider credentials, VPS passwords, cert private keys, or API
  tokens in this document.

## Borrowing Boundary

FreeDomain contributes operational discipline: ownership records, DNS review,
public smoke checks, and abuse/misconfiguration guardrails. LiMa does not build
or join a public domain registration platform.
