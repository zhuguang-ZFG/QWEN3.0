# OpenObserve Setup (PE-C-2)

> **Status:** Active | **Created:** 2026-05-26  
> **Scope:** 24h+ 历史日志/trace 明细；**不改** LiMa 路由；Telegram digest 仍做摘要告警。

## 选型（C-2.1）

| 方案 | 结论 |
|------|------|
| **OpenObserve** | **默认** — 单体 Docker、JSON ingest、低资源；适合 LiMa VPS |
| SigNoz | 后置 — trace 更强；OpenObserve 不满足时再评 |

## 架构

```text
lima-router journal / LiMaEvent
  → observability/openobserve_sink.py (OPENOBSERVE_ENABLED=1)
  → POST /api/{org}/{stream}/_json
  → OpenObserve @ 127.0.0.1:5080

Operator
  → SSH -L 5080:127.0.0.1:5080
  → UI 查询 request_id / task_id / backend_error
```

**与 Telegram：** digest = 摘要；OpenObserve = 可翻 24h 明细。

## 本地 / VPS Docker

```powershell
cd D:\GIT\infra\openobserve
$env:OPENOBSERVE_PASSWORD = "your-local-password"
docker compose up -d
```

VPS 一键：

```powershell
python scripts/install_openobserve_vps.py
python scripts/smoke_openobserve_vps.py
```

首次安装后 root 密码写入 `/opt/lima-openobserve/.env`。**注意：** 数据卷持久化后改密码需 `docker compose down -v` 重建卷，或使用 UI 改密。

默认开发密码：`change-me-local`（生产务必更换）。

## LiMa 环境变量

```env
OPENOBSERVE_ENABLED=0
OPENOBSERVE_URL=http://127.0.0.1:5080
OPENOBSERVE_ORG=default
OPENOBSERVE_STREAM=lima_events
OPENOBSERVE_USER=root@example.com
OPENOBSERVE_PASSWORD=
```

启用后 `observability.metrics.record()` 会将 `LiMaEvent` 异步 best-effort 写入 OpenObserve。

## Journal 补 ship（C-2.3）

```bash
python scripts/ship_lima_journal_openobserve.py --since "1 hour ago" --limit 200
```

从 `journalctl -u lima-router` 拉取结构化 JSON 行写入 `lima_journal` stream（可选 `OPENOBSERVE_JOURNAL_STREAM`）。

## Operator 场景（C-2.5）

| 场景 | 查询提示 |
|------|----------|
| FRP down | `stream=lima_journal` + `message LIKE frp` 或 `unit=frpc` |
| Redis OOM | `message LIKE OOM` OR `message LIKE redis` |
| DG WSS 断连 | `message LIKE device_gateway` OR `event_type=backend_error` + `backend` |

按 **request_id** / **task_id**：LiMaEvent 字段 `request_id`；correlation API 仍用于实时，OpenObserve 用于历史。

## 验收

- [ ] `docker compose up` + UI login
- [ ] `scripts/smoke_openobserve_vps.py` → smoke_ok
- [ ] 启用 `OPENOBSERVE_ENABLED=1` 后产生 `lima_events` 记录
- [ ] journal ship 可写入 24h 内错误行

## 回滚

```bash
docker compose -f infra/openobserve/docker-compose.yml down
OPENOBSERVE_ENABLED=0
```

## 参考

- [OpenObserve JSON ingest](https://openobserve.ai/docs/reference/api/ingestion/logs/json/)
- `observability/openobserve_sink.py`
