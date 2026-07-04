# 05 · 部署与运维分册

> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`，以小智官方云承载语音/对话/LLM，以 DLC 核心承载写字/绘图/路径/设备控制。**
> 关联：`docs/xiaozhi-cloud/README.md`、`00-roadmap.md`、`01-architecture.md`、`02-service-refactor.md`
> 阶段：本分册面向 **P3（安全与可运维）**，P0/P1 阶段仅需本地 `uvicorn` 起服务，无需读本分册的双云部分。

---

## 1. 本分册目的

明确瘦身后 DLC 服务的部署拓扑、双云职责、部署脚本、观测与回滚，避免 P3 阶段临时拍脑袋。

**范围边界：**

- 本分册只写**部署与运维**，不写业务接口（见 `02-service-refactor.md`）。
- 本分册不改任何生产配置，只做设计冻结。真正部署必须在真实 VPS 验证（AGENTS.md 硬规则：禁止自动降级验证）。

---

## 2. 双云职责（延续总设计 §1.5）

| 服务器 | 角色 | 运行服务 |
|--------|------|----------|
| 阿里云 `47.112.162.80` | Public entry / edge | nginx（TLS 终止）、`dlc_api`、`dlc_mcp` 接入、`chat.donglicao.com` 入口 |
| JDCloud `117.72.118.95` | Backend / data / observability | MySQL、Redis、Prometheus、Grafana、后台任务、可选 `dlc_api` hot-standby |

内网互联：Tailscale（延续现状，不新建）。

```text
Internet
   │  chat.donglicao.com
   ▼
阿里云 47.112.162.80  (nginx :443 → 127.0.0.1:8080 dlc_api)
   │  Tailscale 内网
   ▼
JDCloud 117.72.118.95  (MySQL / Redis / Prometheus / Grafana / 后台任务)
```

> **待决策（见 `08-open-questions.md` Q-11）：** `dlc_mcp` broker 是否需要在 JDCloud 做灾备。P3 决策，默认阿里云单点 + 本地桥接。

---

## 3. 部署脚本现状（已核对真实存在）

瘦身**不新写部署框架**，复用现有 `scripts/deploy_unified.py`（Ponytail：能复用就不重写）。

| 脚本 | 职责 |
|------|------|
| `scripts/deploy_unified.py` | 统一部署入口，支持 `--slice` / `--files` / `--dry-run` |
| `scripts/deploy_unified_common.py` | `SLICE_FILES`、`TARGET_ALIYUN`、`TARGET_JDCLOUD`、runtime 文件收集 |
| `scripts/deploy_unified_preflight.py` | 远端备份、回滚 |
| `scripts/deploy_unified_deploy.py` | 文件传输 |
| `scripts/deploy_unified_nginx.py` | nginx 配置 |
| `scripts/deploy_unified_restart.py` | 服务重启 |
| `scripts/verify_production_deploy.py` | 生产部署验证 |
| `scripts/deploy_aliyun_pilot.py` | 阿里云 pilot 部署 |
| `scripts/deploy_jdcloud_probe.py` | JDCloud 探针部署 |

**常用命令（来自 AGENTS.md）：**

```powershell
# 部署 core 切片（含后端运行时与静态资源）
python scripts/deploy_unified.py --slice core

# 干跑，查看将部署哪些文件
python scripts/deploy_unified.py --dry-run

# 部署后验证
python scripts/verify_production_deploy.py
```

---

## 4. P3 部署改造点

### 4.1 新增 DLC 生产入口

P2 已新增 `server_dlc.py`（见 `02-service-refactor.md` §5）。P3 部署要点：

- `server_dlc.py` 仅监听 `127.0.0.1:8080`（安全底线，公网必须经 nginx TLS 终止）。
- nginx 增加 `/dlc/*` 与 MCP 接入的 location（若采用模式 B 自托管 mcp-endpoint-server）。
- 旧 `server.py`（chat/LLM 入口）在 P4 前保持可回滚，不立即删除。

### 4.2 部署切片调整

P3 需要在 `scripts/deploy_unified_common.py` 的 `SLICE_FILES` 增加 `dlc` 切片：

```python
# 设计意图（P3 实现时添加）
SLICE_FILES["dlc"] = [
    "server_dlc.py",
    "dlc_api/",
    "dlc_core/",
    "dlc_mcp/",
    "xiaozhi_drawing/",
    # 保留的设备网关依赖见 02-service-refactor.md §5.3
]
```

> 冻结约束：`dlc` 切片只包含 DLC 主链路 + 保留的设备网关依赖，不含 chat/routing/backends 子系统。

### 4.3 .env 合并而非覆盖（AGENTS.md 硬规则）

部署前必须备份 VPS 的 `.env`，追加新变量，绝不 `sftp.put` 覆盖。P3 新增变量：

| 变量 | 用途 |
|------|------|
| `DLC_API_URL` | `dlc_mcp` 调用 `dlc_api` 的地址（默认 `http://127.0.0.1:18080`，生产改 8080） |
| `LIMA_DEVICE_TOKENS` | dev/应急 fallback per-device token（生产优先查 `v2_device_token` 表） |
| `MCP_ENDPOINT` | 模式 A 官方云接入点或模式 B 自托管地址 |

---

## 5. 观测与健康

### 5.1 健康检查

```bash
curl -sf https://chat.donglicao.com/health
# 期望：{"status":"ok","service":"dlc-drawing","version":"..."}
```

P0 已实现 `/health`（见 `09-p0-evidence.md`）。

### 5.2 Prometheus 指标（保留现有）

- `device_gateway` 现有指标（任务下发/队列深度）通过 `observability/prometheus_metrics.py` 暴露。
- JDCloud 上 Prometheus + Grafana 保留，不新建观测栈。

### 5.3 关键监控项（P3 定义验收阈值）

| 指标 | 含义 | 告警方向 |
|------|------|----------|
| `dlc_api` `/health` | 服务存活 | 连续失败告警 |
| 任务队列深度 | pending 积压 | 持续增长告警 |
| 设备在线率 | registry 会话数 | 骤降告警 |
| 任务失败率 | failed / total | 超阈值告警 |

---

## 6. 回滚

### 6.1 自动备份

`scripts/deploy_unified_preflight.py` 在部署前自动备份到 VPS `/opt/lima-router/backups/`。

### 6.2 回滚步骤

```powershell
# deploy_unified.py 内置 restore_remote_backup；部署失败自动回滚上一版本
# 手动回滚：SSH 到 VPS，从 /opt/lima-router/backups/ 恢复
```

### 6.3 回滚安全约束（AGENTS.md 硬规则）

- 禁止 force-push / reset 用户工作区。
- 回滚只针对部署产物，不动 Git 历史。
- 回滚后必须重跑 `/health` 与冒烟。

---

## 7. 部署验证矩阵（P3 交付）

| 验证项 | 方式 | 通过标准 |
|--------|------|----------|
| 本地健康 | `curl 127.0.0.1:8080/health` | 200 + 正确 JSON |
| 公网健康 | `curl https://chat.donglicao.com/health` | 200（真实域名，非 localhost） |
| MCP 接入 | 官方云/桥接 discovery | 成功列出 DLC tool |
| 任务下发 | 真实设备或假设备 | 收到任务并回 done |
| 回滚 | 手动触发 | 恢复上一版本且健康 |

> AGENTS.md 硬规则重申：**VPS 部署必须在真实 VPS 验证，不能仅在 localhost 验证公网 API。**

---

## 8. 与其他分册的边界

- 失败恢复、防呆、安全边界 → `06-failure-and-safety.md`
- 验收矩阵总表 → `07-validation-and-acceptance.md`
- 服务端接口 → `02-service-refactor.md`

---

## 9. 本分册状态

- 阶段：P3 设计冻结（部署/观测/回滚）
- 部署脚本：复用现有 `deploy_unified.py`，仅增 `dlc` 切片
- 未决项：`dlc_mcp` 是否灾备（Q-11）
