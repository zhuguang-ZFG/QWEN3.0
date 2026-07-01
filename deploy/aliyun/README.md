# Aliyun LiMa Router Pilot

阿里云辅助节点部署包。京东云为主节点，阿里云 pilot 只处理无状态的免费/低价后端流量。

## 文件说明

| 文件 | 用途 |
|---|---|
| `lima-router-pilot.service` | systemd 服务单元 |
| `install_aliyun_pilot.sh` | 在阿里云 VPS 上执行的安装脚本 |
| `aliyun-pilot.nginx.conf` | nginx server block 模板 |
| `README.md` | 本文件 |

## 快速部署

```bash
# 本地执行（需要 SSH key 或 LIMA_ALIYUN_PASSWORD）
python scripts/deploy_aliyun_pilot.py
```

## 手动部署

```bash
# 1. 把仓库同步到阿里云 /opt/lima-router-pilot/repo/
# 2. 在阿里云上以 root 执行
bash /opt/lima-router-pilot/repo/deploy/aliyun/install_aliyun_pilot.sh

# 3. 配置 nginx（可选，先用于 aliyun.donglicao.com 验证）
cp /opt/lima-router-pilot/repo/deploy/aliyun/aliyun-pilot.nginx.conf \
   /etc/nginx/conf.d/aliyun-pilot.donglicao.com.conf
nginx -t && systemctl reload nginx
```

## 验证

```bash
# 本地 loopback
ssh root@47.112.162.80 'curl -sf http://127.0.0.1:8080/health'

# 公网（配置 DNS 后）
curl -sf https://aliyun.donglicao.com/health
```

## 环境变量

 pilot 默认关闭以下有状态能力：

- `LIMA_NODE_ROLE=free_backend_only`
- `LIMA_SESSION_MEMORY_ENABLED=0`
- `LIMA_DEVICE_GATEWAY_ENABLED=0`
- `LIMA_MQTT_CLIENT_ENABLED=0`
- `LIMA_CONTEXT_RETRIEVAL_ENABLED=0`
- `LIMA_PROMETHEUS_ENABLED=0`
- `LIMA_ALERT_EVALUATOR_ENABLED=0`
- `LIMA_DEVICE_*_STORE=memory`

付费/需要本地代理的后端不会在 pilot 上被选中；只使用云上免费后端（Pollinations、DDG、OVH、Google Flash 等）。
