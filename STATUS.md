# LiMa Code CLI — 运行状态

> 更新: 2026-06-02
> VPS: `47.112.162.80` | 仓库: `github.com/zhuguang-ZFG/QWEN3.0`

## 部署状态

| 服务 | 端口 | 状态 |
|---|---|---|
| lima-router | 8080 | ✅ 运行中 |
| scnet-large (SCNet) | 4505 | ✅ HEALTHY |
| kimi-proxy (Kimi) | 4504 | ✅ HEALTHY |
| mimo-proxy (MiMo) | 4507 | ✅ HEALTHY |
| longcat-web-proxy | 4506 | ✅ HEALTHY |
| keepalive cron | — | ✅ 每 30 分钟 |

## 能力矩阵（已验证）

| 能力 | SCNet | Kimi | MiMo | LongCat |
|---|---|---|---|---|
| 基础对话 | ✅ | ✅ | ✅ | ✅ |
| 联网搜索 | ✅ | ✅(search) | ❌ | ❌ |
| Thinking | N/A | ✅ | ✅ | ✅ |
| 长上下文文件桥接 | ✅ 500K | ⚠️ | ⚠️ | ⚠️ |
| 工具调用(文本提取) | ❌ 平台限制 | ✅ | ✅ | ✅ |
| Cookie 自动刷新 | ❌ | ❌ | ❌ | ✅ Playwright |

## Cookie 有效期

| 后端 | 当前 Cookie | 过期 | 剩余 |
|---|---|---|---|
| SCNet | `cpk.json` (11 cookies) | session 型 | 不确定 |
| Kimi | `kimi.txt` → JWT | 2027-06-01 | ~364 天 |

## 最近变更 (2026-06-02)

| 变更 | 文件 |
|---|---|
| SCNet 文件桥接修复 | `reverse_gateway/providers/scnet.py` |
| SCNet 工具检测自动禁用联网 | `reverse_gateway/providers/scnet_adapter.py` |
| 增强工具 system prompt | `text_tool_extractor.py`, `routes/tool_forward.py` |
| Kimi v2 代理 (工具转发+历史) | `infra/kimi_proxy_v2.js` |
| 健康监控完善 | `scripts/reverse_proxy_keepalive.py` |
| Kimi Cookie 部署脚本 | `scripts/provision_kimi_cookies.py` |
| VPS 上下文扩容 50K→500K | `.env` |

## 文件统计

- Python 源文件: ~200+
- 测试: 1481+ passed
- 逆向后端: 4 个
- 总模型数: 50+
