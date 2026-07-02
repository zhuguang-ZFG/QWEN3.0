# LiMa（力码）—— AI 智能硬件云端服务

> 深圳市动力巢科技有限公司（www.donglicao.com）

LiMa 是一个多后端 AI 路由服务器，同时为 AI 绘图机、写字机、2D 数字人等智能硬件提供云端控制平面。

- **AI 路由**：根据请求类型、健康状态、预算与质量评分，智能路由到 170+ 个 AI 后端（Groq、NVIDIA、OpenRouter、DeepSeek、Cloudflare、阿里云等）。
- **设备云端**：为 ESP32 绘图机/写字机提供任务派发、路径规划、状态监控与 OTA。
- **公网入口**：https://chat.donglicao.com（支持匿名免费聊天，无需 API Key）。

---

## 技术栈

- **运行时**：Python 3.10 + FastAPI + uvicorn
- **HTTP 客户端**：httpx
- **数据**：SQLite（语义缓存、会话记忆）、Redis（设备任务队列）
- **通信**：WebSocket / MQTT（设备双向通信）
- **代码检查**：ruff（目标 py310，行宽 120）
- **类型检查**：pyright
- **测试**：pytest（asyncio_mode=auto）
- **容器**：Docker + docker-compose

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_server.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少设置 LIMA_API_KEYS、CLOUDFLARE_ACCOUNT_ID、CLOUDFLARE_TOKEN
```

### 3. 启动服务

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8080
```

### 4. 健康检查

```bash
curl http://127.0.0.1:8080/health
```

---

## 主要 API

### OpenAI 兼容聊天

```bash
POST /v1/chat/completions
```

示例：

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -d '{
    "model": "lima-1.3",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 设备网关

```bash
GET  /device/v1/health           # 设备网关健康
POST /device/v1/tasks            # 下发任务（写字/绘图/控制）
GET  /device/v1/tasks/{task_id}  # 查询任务
WS   /device/v1/ws               # 设备 WebSocket 长连接
```

### 管理端点

```bash
GET /v1/status        # 后端与熔断状态（需 private API key）
GET /health           # 服务健康
```

---

## 部署

### 本地开发

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8080
```

### 生产部署（VPS）

```bash
# 标准全量部署
python scripts/deploy_unified.py --slice core

# 仅上传指定文件（不重启）
python scripts/deploy_unified.py --files <file1> <file2> --no-restart

# 仅检查会部署哪些文件
python scripts/deploy_unified.py --dry-run
```

部署依赖 `.env` 中的 `LIMA_DEPLOY_KEY_PATH` 与 `LIMA_DEPLOY_USE_TAR=1`。

详见 [`docs/DEPLOY_AND_RELEASE_CONVENTION.md`](docs/DEPLOY_AND_RELEASE_CONVENTION.md)。

---

## 项目结构

```
.
├── server.py                  # FastAPI 入口
├── server_bootstrap.py        # 运行时常量与终极降级
├── server_lifespan.py         # 异步生命周期
├── routing_engine.py          # AI 路由权威入口
├── router_v3/                 # 后端池
├── routing_selector/          # 后端排序与选择
├── routing_executor.py        # 后端执行（串/并行 + 降级）
├── http_caller.py             # HTTP 传输层
├── backends_registry/         # 170+ 后端注册
├── routes/                    # FastAPI 路由
│   ├── chat_endpoints.py
│   ├── device_gateway*.py
│   ├── device_app_*.py
│   ├── device_ota_app.py
│   ├── system_endpoints.py
│   └── xiaozhi_compat/        # 小智 App 兼容层（默认关闭）
├── device_gateway/            # 设备协议、任务、路径规划
├── device_logic/              # 账号、鉴权、设备数据逻辑
├── session_memory/            # 持久记忆与学习循环
├── context_pipeline/          # 检索与上下文注入（编码模块已退役）
├── skills/                    # 可注入技能 Markdown
├── chat-web/                  # Web 聊天控制台
├── donglicao-site-v2/         # 官网 Next.js 站点
├── docs-site/                 # VitePress 开发者文档站
├── sdk/                       # Python/JS/Go 官方 SDK
├── scripts/                   # 工具、部署、冒烟脚本
├── tests/                     # 测试套件
└── docs/                      # 文档索引与架构说明
```

---

## 核心文档

| 文档 | 说明 |
|------|------|
| [`STATUS.md`](STATUS.md) | 当前项目状态、已完成里程碑、部署健康 |
| [`AGENTS.md`](AGENTS.md) | 开发约定、命令、Git/部署规则 |
| [`CLAUDE.md`](CLAUDE.md) | 精简开发规则与仓库统计 |
| [`docs/README.md`](docs/README.md) | 文档索引与必读顺序 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 系统架构与模块边界 |
| [`docs/REQUEST_PIPELINE_AUTHORITY_CN.md`](docs/REQUEST_PIPELINE_AUTHORITY_CN.md) | 18 步请求处理管线 |
| [`docs/DEPLOY_AND_RELEASE_CONVENTION.md`](docs/DEPLOY_AND_RELEASE_CONVENTION.md) | 部署与发布约定 |
| [`docs/DEVICE_DEVELOPER_GUIDE_CN.md`](docs/DEVICE_DEVELOPER_GUIDE_CN.md) | 设备开发、联调、验证入口 |
| [`docs/archive/strategic-plans-2026-06/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/archive/strategic-plans-2026-06/PROJECT_OPTIMIZATION_ROADMAP_CN.md) | 历史路线图（已归档） |

---

## 开发规范

- Python 3.10+ 类型注解
- 单文件 ≤300 行，函数 ≤50 行
- 禁止裸 `except Exception: pass`
- 新能力默认关闭，需显式 env flag 开启
- 文档类产物默认使用中文

完整规范见 [`AGENTS.md`](AGENTS.md)。

---

## 测试

```bash
# 全量测试
python -m pytest --tb=short -q

# 聚焦测试
python -m pytest tests/test_routing_engine.py -v

# 预提交门禁
python scripts/run_pre_commit_check.py --full
```

---

## 退役说明

以下模块已移除或归档：

- Telegram bot/operator 通知
- GitHub/Gitee webhook 路由
- Anthropic `/v1/messages` 兼容层
- `channel_gateway`（微信绑定层）
- `lima_mcp/` HTTP MCP 路由

详见 [`STATUS.md`](STATUS.md)「退役模块」。

---

## 许可证

MIT License

---

**LiMa —— 让 AI 硬件更智能。**
