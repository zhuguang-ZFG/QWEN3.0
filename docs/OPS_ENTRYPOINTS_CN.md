# LiMa 运维入口

> 已被 `docs/ONLINE_DISTRIBUTIONS.md` 取代和扩展。

## 目的

本文件保留了最初受 FreeDomain 启发的计划目标名称。VPS 托管公共服务面的当前权威来源现在是 `docs/ONLINE_DISTRIBUTIONS.md`，涵盖了官方网站、开放平台、聊天界面、FRP 端点、nginx 边缘和服务快照。

## 当前入口

| 名称 | URL | 所有者 | 健康检查 | 认证 |
|---|---|---|---|---|
| 官方网站 | `https://www.donglicao.com` | lima | `/` | 公开 |
| 主聊天/API | `https://chat.donglicao.com` | lima | `/health` | API 调用需私钥 |
| 开放平台 | `https://api.donglicao.com` | lima | `/` | New API Token |
| FRP 验证 | `http://47.112.162.80:8088` | lima | `/health` | API 调用需私钥 |

## 规则

- 公开 API 流量应优先通过 nginx 的 HTTPS。
- `8080`、`3003`、`8091` 等内部服务端口不得直接暴露在公网上。
- `/health` 和 `/v1/models` 可保持公开以便可用性监控和 IDE 发现。
- `/v1/chat/completions`、`/v1/messages`、Agent 路由、live-key/status 和图像生成需要私有访问。
- DNS、FRP、VPS、nginx、systemd、证书及公共服务面变更应记录在 `docs/ONLINE_DISTRIBUTIONS.md`、`infra/vps/`、`STATUS.md`、`docs/LIMA_MEMORY.md` 和 `progress.md` 中。
- 不得在本文件中存储提供商凭证、VPS 密码、证书私钥或 API Token。

## 借鉴边界

FreeDomain 贡献了运维纪律：所有权记录、DNS 审查、公开烟雾检查以及滥用/错误配置护栏。LiMa 不构建也不加入公开域名注册平台。
