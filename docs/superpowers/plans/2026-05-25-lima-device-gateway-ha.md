# LiMa Device Gateway HA Plan

**Date:** 2026-05-25
**Status:** Redis-backed runtime slice deployed on VPS

## Goal

Make `/device/v1/*` safe to run with multiple LiMa router processes or nodes
without losing tasks when the HTTP task producer and the device WebSocket owner
land on different workers.

## Runtime Decision

Use Redis for the realtime control plane:

- shared task ids;
- task state snapshots and motion events;
- per-device pending queues;
- task-available pub/sub notifications.

Keep Postgres out of the realtime path for this slice. It remains the better
fit for later long-retention audit/history once the live protocol is stable.

## Routing Strategy

Every router process keeps only its local WebSocket objects in memory. When a
task is created by `/device/v1/tasks` and the target device is not connected to
that same process, the process enqueues the task in Redis and publishes a
`task_available` message. All router processes subscribe; only the process that
has the local WebSocket session drains the device queue and sends the task.

If the device reconnects after a missed pub/sub message, the `hello` path still
drains the Redis queue, so pub/sub is an acceleration mechanism rather than the
only correctness path.

## HA Environment

Default local/single-node mode:

```text
LIMA_DEVICE_TASK_STORE=
LIMA_DEVICE_SESSION_BUS=
LIMA_DEVICE_REDIS_URL=
```

Redis HA mode:

```text
LIMA_DEVICE_TASK_STORE=redis
LIMA_DEVICE_SESSION_BUS=redis
LIMA_DEVICE_REDIS_URL=redis://127.0.0.1:6379/0
```

The Python `redis` package must be installed in the router runtime before HA
mode is enabled.

## Remaining Gates

- Increasing the main `lima-router.service` worker count remains a separate
  rollout decision. The deployed verification used a temporary private second
  router process on `127.0.0.1:18080`.
- Long-term task/audit retention should move to Postgres or an append-only
  event table after the hardware protocol stabilizes.
- Multi-node deployment should use a private Redis endpoint and firewall rules;
  direct public access to Redis must stay closed.

## Deployment Evidence

- Code backup: `/opt/lima-router/backups/codex-device-ha-20260525_015208`.
- Env backup:
  `/root/secure-service-backups/lima-router.env.codex-device-ha-20260525_015208`.
- Redis config backup:
  `/root/secure-service-backups/redis.conf.codex-device-ha-20260525_015305`.
- Focused Device Gateway suite: `31 passed`.
- Online distribution smoke: `12/12` including public `6379` guard.
- Cross-process smoke: a task created by a private temp router on
  `127.0.0.1:18080` was delivered to the public WebSocket session through Redis
  pub/sub.
