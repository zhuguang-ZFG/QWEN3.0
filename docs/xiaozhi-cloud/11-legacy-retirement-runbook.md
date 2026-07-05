# D-3b 旧系统退役 Runbook（生产切换，不可逆，需人工在场）

> 本文档记录「瘦身工程 D-3b 阶段」在 VPS 上退役旧 `server:app`、切到新 `server_dlc:app` 的**安全执行顺序**。
> 所有事实均为 2026-07 SSH 实测核查结果。**这是不可逆生产操作，必须人工在场、逐步执行、每步验证后再走下一步。**

---

## 一、为什么不能用默认 `deploy_unified.py` 一把梭

本会话核查发现两个会直接搞垮生产的隐患，标准部署流程在此不安全：

### 隐患 1：新旧服务共享同一目录

```
lima-router.service   ExecStart=uvicorn server:app      WorkingDirectory=/opt/lima-router  (:8080 旧，生产主处理器)
dlc-drawing.service   ExecStart=uvicorn server_dlc:app  WorkingDirectory=/opt/lima-router  (:8081 新，仅 /dlc/)
```

两个服务从**同一个 `/opt/lima-router`** 跑。仓库已删的配置字段（`routing_guard_*`/`structured_logging`/`alert_evaluator`）和模块，旧系统仍在引用：

```
/opt/lima-router/server_lifespan_phases.py               → routing_guard / structured_logging / alert_evaluator
/opt/lima-router/observability/{alert_evaluator,routing_guard,structured_logging}.py
```

→ 一旦把瘦身后代码部署进共享目录，正在服务生产的旧 `server:app`(:8080) 下次 reload/重启会 `AttributeError` 崩溃。

### 隐患 2：deploy 脚本重启的是错的服务

`scripts/deploy_unified_restart.py` 硬编码 `systemctl restart lima-router`（旧服务），根本不重启要更新的 `dlc-drawing`(:8081)。默认流程 = 铺新代码 → 重启旧服务 → 旧系统加载已删字段 → 崩。

---

## 二、切换前置事实（2026-07 实测，两节点 aliyun 47.112.162.80 / jdcloud 117.72.118.95 一致）

- nginx `chat.donglicao.com`：`/dlc/*` → :8081；**其余全部**（`/chat/ /admin /api/ /agent/ /device/ /device/v1/ws /digital-human/ /fleet/ /v1/voice /v1/`）→ :8080 旧系统
- 小程序 v3.9.0 真实后端调用**只有** `/device/v1/app/*`（`@/api/` 是前端源码别名，非后端路径）
- `lima-router`(:8080) + `dlc-drawing`(:8081) 均 active，health 均 200
- VPS :8081 当前跑**旧 server_dlc 代码**（无 `register_device_app`，`dlc_api/device_app_router.py` MISSING）——阶段A/绘图恢复代码尚未部署

---

## 三、安全执行顺序（与 deploy 脚本默认相反：先退役旧系统，再部署新代码）

### 步骤 0：备份（每节点）
```bash
ts=$(date +%Y%m%d_%H%M%S)
cp -a /opt/lima-router /opt/lima-router.bak.$ts          # 或至少备份 .env + systemd unit
cp /etc/systemd/system/lima-router.service /root/lima-router.service.bak.$ts
cp /etc/nginx/conf.d/chat.donglicao.com.conf /root/chat.conf.bak.$ts
cp /opt/lima-router/.env /root/lima-env.bak.$ts
```

### 步骤 1：先把新代码部署到一个独立目录（不覆盖共享目录，避免隐患 1）
- 方案：把 `dlc-drawing` 的 `WorkingDirectory` 改到独立目录（如 `/opt/dlc-drawing`），部署瘦身代码到那里，:8081 重启后验证；旧 :8080 目录不动、继续服务。
- 或：先执行步骤 2/3 停掉旧系统，使 `/opt/lima-router` 不再有旧读者，再直接部署（更简单但切换窗口内 :8080 功能短暂不可用）。

### 步骤 2：先切 nginx，把非 /dlc 流量导到 :8081
把 `/device/`（尤其 `/device/v1/app/`）、以及仍需的 `/admin`、`/api` location 的 `proxy_pass` 从 `127.0.0.1:8080` 改为 `127.0.0.1:8081`；
已退役功能（`/chat/ /agent/ /digital-human/ /fleet/ /v1/voice`）的 location 删除或返回 410。
```bash
nginx -t && systemctl reload nginx
```

### 步骤 3：验证 :8081 承载小程序 API（切流后立即冒烟）
```bash
curl -s https://chat.donglicao.com/dlc/health
curl -s -o /dev/null -w "%{http_code}\n" https://chat.donglicao.com/device/v1/app/devices   # 需带合法 Bearer
# 重点验证恢复的绘图端点：
#   /device/v1/app/images/generations
```

### 步骤 4：停旧服务
```bash
systemctl stop lima-router && systemctl disable lima-router
systemctl is-active dlc-drawing        # 确认新服务稳定
```

### 步骤 5：清理共享目录旧文件（旧系统已停，安全）
```bash
cd /opt/lima-router
rm -f server.py server_lifespan.py server_lifespan_phases.py server_bootstrap.py server_context.py server_lifespan_state.py
# observability/ 下已退役模块同理（对照仓库当前状态）
```

### 步骤 6：最终冒烟 + 回滚预案
- 冒烟：`chat.donglicao.com/dlc/health` + 小程序真机走一遍绑定/任务/绘图。
- 回滚：`systemctl start lima-router` + nginx 配置回滚（步骤 0 备份）+ `systemctl restart nginx`。

---

## 四、注意
- 两个节点（aliyun + jdcloud）都要执行；jdcloud 是 `chat.donglicao.com` 生产入口。
- `.env` 合并不覆盖（部署硬规则）。
- 全程人工在场，每步验证通过再走下一步。
