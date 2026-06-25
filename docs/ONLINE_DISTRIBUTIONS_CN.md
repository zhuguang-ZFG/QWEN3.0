# LiMa 在线分布

> 更新时间: 2026-06-15
> 范围: LiMa 项目 VPS 托管公共服务面
> 项目定位: AI 智能设备统一云端服务

## 规则

官方网站、聊天界面、设备网关、FRP 端点、nginx 边缘及支撑公共服务均属于 LiMa 分布。

禁止提交密钥、证书私钥、提供商令牌、数据库转储、生成的 `.next/`、`node_modules/` 或本地二进制/软件下载。

## 清单

| 服务面 | 公开 URL | 用途 |
|---|---|---|
| 官方网站 | `https://www.donglicao.com`、`https://donglicao.com` | 公共产品/品牌入口和演示 |
| 聊天界面 | `https://chat.donglicao.com` | OpenAI 兼容 API 和设备边缘 |
| 设备网关 | `https://chat.donglicao.com/device/v1/*` | ESP32 设备通信 |
| 开放平台 | `https://api.donglicao.com` | 京东云 NewAPI 反代（非 LiMa Server 直接入口） |
| FRP 端点 | `http://47.112.162.80:8088` | Windows 本地路由器验证路径 |
| 京东云节点 | `117.72.118.95` | 辅助提供商探测/监控节点 |

## 边缘策略

- 公开 HTTPS 经 nginx 在 `80` 和 `443` 端口提供服务
- FRP 公开验证使用 `8088` 端口
- 内部服务端口的直接公开访问必须通过防火墙保持阻断
- `/device/v1/*` 仅通过 `chat.donglicao.com` 公开，要求设备令牌认证

## 密钥策略

- nginx 快照可包含证书路径，但绝不包含私钥材料
- systemd unit 文件不得包含提供商密钥、Bot Token、API Token 或密码
- 服务密钥应存放于 VPS 上仅 root 可读的环境文件中
