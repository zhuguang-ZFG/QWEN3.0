# DLC 绘图服务 —— ESP32 绘图机/写字机云端

> 深圳市动力巢科技有限公司（www.donglicao.com）

DLC 绘图服务为 ESP32 绘图机、写字机提供云端路径生成、任务下发与设备管理能力。通过 MCP 协议与小智官方云集成，支持语音控制绘图/写字。

- **绘图/写字核心**：文本绘图、写字、图生路径与路径校验
- **设备云端**：任务派发、设备状态、小程序 App API、图库
- **公网入口**：https://chat.donglicao.com/dlc/*（nginx → `server_dlc` :8081）

---

## 技术栈

- **运行时**：Python 3.10 + FastAPI + uvicorn
- **HTTP 客户端**：httpx
- **数据**：SQLite（设备/会话数据）、Redis（设备任务队列）
- **图生**：DashScope/wanx（`dashscope_image_client.py`）
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
# 编辑 .env，至少设置 LIMA_API_KEY / LIMA_API_KEYS
```

### 3. 启动服务

```bash
python -m uvicorn server_dlc:app --host 127.0.0.1 --port 8081
```

### 4. 健康检查

```bash
curl http://127.0.0.1:8081/health
```

---

## 主要 API

### DLC 任务（需 `Authorization: Bearer <LIMA_API_KEY>`）

```bash
POST /dlc/tasks/draw          # 文本绘图预览
POST /dlc/tasks/write         # 写字预览
POST /dlc/tasks/dispatch      # 下发任务到设备
POST /dlc/tasks/validate      # 校验运动路径
GET  /dlc/devices/{id}/status # 设备状态
```

示例：

```bash
curl -s http://127.0.0.1:8081/dlc/tasks/validate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -d '{"path":[{"x":0,"y":0},{"x":10,"y":10}]}'
```

### 微信小程序设备 App

```bash
POST /device/v1/app/voice/transcribe   # 按住说话 → ASR + intent
POST /device/v1/app/voice/ticket       # 换取 WS ticket
WS   /device/v1/app/voice/ws           # 实时流 ASR（ticket 鉴权）
WS   /v1/voice                         # M2 兼容别名
GET  /device/v1/app/*                  # 其他设备 App API
```

详见 [`docs-site/api/voice.md`](docs-site/api/voice.md)。

### 健康检查

```bash
GET /health                   # 服务健康（无需鉴权）
```

---

## 部署

### 本地开发

```bash
python -m uvicorn server_dlc:app --host 127.0.0.1 --port 8081
```

### 生产部署（VPS）

```bash
# 标准全量部署（默认京东云）
python scripts/deploy_unified.py --target jdcloud --slice core

# 语音栈增量
python scripts/deploy_unified.py --target jdcloud --files routes/device_app_voice.py device_voice/

# 生产语音 strict E2E
LIMA_VOICE_E2E_STRICT=1 python scripts/run_voice_e2e_production.py
```

部署依赖 `.env` 中的 `LIMA_JDCLOUD_ROOT_PASSWORD`（或 `LIMA_DEPLOY_KEY_PATH`）；默认 tar 批量上传，无需再设 `LIMA_DEPLOY_USE_TAR=1`。

详见 [`docs/DEPLOY_AND_RELEASE_CONVENTION.md`](docs/DEPLOY_AND_RELEASE_CONVENTION.md)。

---

## 项目结构

```
.
├── server_dlc.py              # 生产 FastAPI 入口（:8081）
├── dlc_api/                   # DLC HTTP 路由与小程序 App 聚合
├── dlc_core/                  # 绘图/写字/下发核心
├── dlc_mcp/                   # 小智云 MCP JSON-RPC
├── device_gateway/            # Redis 任务队列、WS、设备状态
├── device_voice/              # 小程序语音 ASR（REST/WS）
├── routes/                    # 设备 App、语音、图库等路由
├── dashscope_image_client.py  # 图生后端
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
| [`docs/DEPLOY_AND_RELEASE_CONVENTION.md`](docs/DEPLOY_AND_RELEASE_CONVENTION.md) | 部署与发布约定 |
| [`docs/DEVICE_DEVELOPER_GUIDE_CN.md`](docs/DEVICE_DEVELOPER_GUIDE_CN.md) | 设备开发、联调、验证入口 |

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

# DLC API 聚焦
python -m pytest tests/test_dlc_api.py -v

# 预提交门禁
python scripts/run_pre_commit_check.py --full
```

---

## 退役说明

P4/P5 瘦身后已移除旧 LiMa 多后端路由、`server.py`、`routing_engine*`、Chat/Admin 等模块。详见 [`STATUS.md`](STATUS.md) 与 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 许可证

MIT License

---

**DLC —— 让绘图机更智能。**
