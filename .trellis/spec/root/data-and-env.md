# Data & Environment — 数据存储与环境配置

## 数据存储

- **SQLite**：设备/会话数据、语义缓存。
- **Redis**：设备任务队列（主）。任务存储后端经 `device_gateway.store.configure_task_store_from_env()` 在入口 lifespan 配置；启动失败即 fail-fast（见 [error-handling.md](error-handling.md)）。
- 关停时若后端为 redis 需关闭连接池（证据：`server_dlc.py` lifespan 清理段）。

## 配置分层

- 业务配置集中在 `config/` 模块的设置对象，如 `config/voice_settings.py` 的 `VOICE`（`VOICE.enabled`、`VOICE.asr_provider`）；业务模块 import 设置对象，不散写 `os.environ.get`。
- 环境变量权威清单：`.env.example`。

关键变量：

| 变量 | 用途 |
|------|------|
| `LIMA_API_KEY` / `LIMA_ADMIN_TOKEN` | API / 管理鉴权（Bearer） |
| `LIMA_VOICE_ENABLED` | 小程序语音总开关（生产 `1`） |
| `LIMA_VOICE_ASR_PROVIDER` | `dashscope` / `funasr` / `whisper` |
| `DASHSCOPE_ASR_MODEL` | REST 按住说话（默认 `qwen3-asr-flash`） |
| `LIMA_VOICE_STREAM_ASR_MODEL` | WS 流式（空=缓冲模式） |
| `LIMA_STRUCTURED_LOGGING` | `1` 时切结构化日志 |
| `LIMA_JWT_REQUIRE_TYP` | 显式 `0`/`1`；未设时生产默认开，拒无 `typ` 的 device/admin JWT |
| `LIMA_RATE_LIMIT_DISABLE` | 非生产可关限流；**生产忽略**（`runtime_env.rate_limit_disabled`） |
| `LIMA_DEPLOY_KEY_PATH` / `LIMA_DEPLOY_USE_TAR` | 部署 SSH 私钥 / 打包方式 |

## .env 与安全红线

- 部署时 `.env` **只合并不覆盖**：先备份 VPS 现有 `.env`，追加新变量（`docs/DEPLOY_AND_RELEASE_CONVENTION.md` 安全红线）。
- 禁止暂存/提交凭证、`.env`、`.lima-data/`、`client_keys/`。
- Telegram 通知通道已退役，但 `integrations/telegram_bot/` 仍供 gallery 存图，勿误删。
