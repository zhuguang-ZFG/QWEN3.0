# LiMa（力码）—— AI 智能设备云端服务

> 深圳市动力巢科技有限公司 (www.donglicao.com)

**最新更新**: 2026-06-09 战略转型 —— 从个人编码助手后端 → AI 智能设备统一云端服务平台

**核心理念：让 AI 硬件更智能**

为 AI 绘图机、写字机等智能设备提供云端大脑，让每个家庭拥有会画画、会写字的智能伙伴。

---

## 项目定位

LiMa 是 **AI 智能硬件的云端大脑**，为 AI 绘图机、写字机等智能设备提供：

- **智能理解**：自然语言 → 设备指令（AI 驱动）
- **任务编排**：复杂任务分解与执行（绘图路径规划、字体渲染）
- **设备网关**：MQTT 双向通信，实时状态监控
- **多模型路由**：OpenRouter、OpenAI、本地模型智能调度

### 核心场景

1. **AI 绘图机**：「画一只猫」→ SVG 生成 → 路径优化 → G-code → ESP32 执行
2. **AI 写字机**：「写首诗」→ 诗歌生成 → 字体渲染 → 笔画轨迹 → 机械臂书写
3. **未来扩展**：语音交互、视觉识别、多设备协同

---

## 架构（战略转型后）

```
小程序/App/Web 控制台
          │ HTTPS/WebSocket
          ▼
   FastAPI (LiMa Core)
    ┌──────┴──────┐
    │  API Layer  │
    │ - Chat API (OpenAI 兼容)
    │ - Device Gateway (MQTT/WebSocket)
    │ - Task Queue (绘图/写字)
    └──────┬──────┘
    ┌──────┴──────┐
    │ Business Logic │
    │ - AI Router (多模型调度)
    │ - Drawing Engine (SVG → G-code)
    │ - Writing Engine (字体渲染)
    └──────┬──────┘
    ┌──────┴──────┐
    │ Infrastructure │
    │ - SQLite (设备状态/任务队列)
    │ - Prometheus (监控告警)
    └──────┬──────┘
           │ MQTT
           ▼
    ESP32 设备 (绘图机/写字机)
```

---

## 技术栈

- **后端**: Python 3.10 + FastAPI + uvicorn
- **数据库**: SQLite（设备状态、任务队列、会话记忆）
- **通信**: MQTT（设备 ↔ 云端双向）
- **AI**: OpenRouter（多模型聚合）、OpenAI、本地模型
- **部署**: 阿里云 + 京东云（双 VPS 高可用）
- **监控**: Prometheus + Grafana

---

## 支持的设备

- **ESP32 绘图机**：XY 平台，单笔画绘制
- **ESP32 写字机**：中文汉字书写
- **扩展支持**（规划中）：激光雕刻、3D 打印、机械臂

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_server.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 设置 LIMA_API_KEY、OPENROUTER_API_KEY 等
```

### 3. 启动服务

```bash
python server.py
```

服务默认运行在 `http://localhost:8000`

### 4. 健康检查

```bash
curl http://localhost:8000/health
```

---

## API 端点

### OpenAI 兼容端点

```bash
POST /v1/chat/completions
```

支持 OpenAI SDK 直接接入：

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-lima-api-key"
)

response = client.chat.completions.create(
    model="lima-1.3",
    messages=[{"role": "user", "content": "画一只猫"}]
)
```

### 设备网关端点（已实现）

```bash
POST /api/v1/devices/register      # 设备注册
POST /api/v1/devices/bind          # 设备绑定
GET  /api/v1/devices               # 设备列表
POST /device/v1/tasks              # 下发任务
GET  /device/v1/tasks/{task_id}    # 查询任务
POST /device/v1/draw               # 绘图任务
POST /device/v1/write              # 写字任务
```

### 管理端点

```bash
GET  /health               # 健康检查
GET  /admin/status         # 系统状态
GET  /admin/backends       # 后端列表
POST /admin/reload         # 热重载配置
```

---

## 部署

### 本地开发

```bash
python server.py
```

### 生产部署（VPS）

```bash
# 阿里云 VPS
python scripts/deploy_unified.py --target aliyun --profile lima-prod

# 京东云 VPS（备用）
python scripts/deploy_unified.py --target jdcloud --profile lima-probe
```

详见 [DEPLOY_AND_RELEASE_CONVENTION.md](docs/DEPLOY_AND_RELEASE_CONVENTION.md)

---

## 项目结构

```
D:\QWEN3.0\
├── server.py                  # FastAPI 主入口
├── routes/                    # 路由模块
│   ├── device_gateway.py      # 设备网关（Day 3-5 新建）
│   ├── chat_endpoints.py      # Chat API
│   └── admin.py               # 管理端点
├── routing_engine.py          # 多模型路由引擎
├── smart_router.py            # 智能意图理解
├── session_memory/            # 会话记忆
├── device_schema.py           # 设备数据模型（Day 3 新建）
├── migrations/                # 数据库迁移（Day 3 新建）
├── deploy/                    # 部署脚本
├── scripts/                   # 工具脚本
├── tests/                     # 测试
└── docs/                      # 文档
    ├── ESP32S_XYZ_MANAGEMENT.md         # ESP32 管理
    ├── ESP32S_XYZ_INTEGRATION_GUIDE.md  # 设备集成指南
    ├── ESP32S_XYZ_PROTOCOL_ADAPTER_DESIGN.md  # 协议适配设计
    └── ARCHITECTURE.md                  # 系统架构
```

---

## 核心文档

| 文档 | 说明 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | 项目开发规范（必读） |
| [STATUS.md](STATUS.md) | 项目状态 |
| [AGENTS.md](AGENTS.md) | 协作规范 |
| [ESP32S_XYZ_MANAGEMENT.md](docs/ESP32S_XYZ_MANAGEMENT.md) | ESP32 管理 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统架构 |
| [DEPLOY_AND_RELEASE_CONVENTION.md](docs/DEPLOY_AND_RELEASE_CONVENTION.md) | 部署与发布规范 |

---

## 开发规范

### 代码质量

- Python 3.10+ 类型注解
- 单文件 ≤300 行，函数 ≤50 行
- 禁止裸 `except Exception: pass`
- 禁止降级处理（失败必须报错）

### Git 工作流

```bash
# 1. 功能分支开发
git checkout -b feat/your-feature

# 2. 本地测试
pytest

# 3. 提交（包含 Co-Authored-By）
git commit -m "feat: your feature

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"

# 4. 推送 origin（GitHub）
git push origin feat/your-feature

# 5. 同步 gitee
git push gitee feat/your-feature
```

### 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_device_gateway.py

# 覆盖率报告
pytest --cov=. --cov-report=html
```

---

## 战略转型（2026-06-09）

### 从编码助手 → 设备云端服务

**删除的功能**：
- Agent Runtime（自主任务执行）
- Tool Forwarding（工具调用）
- Code Quality Gate（代码质量门控）
- Semantic Cache（语义缓存）

**保留的核心**：
- 多模型路由（OpenRouter、OpenAI、本地模型）
- 设备网关（MQTT 双向通信）
- 会话记忆（SQLite）
- 监控告警（Prometheus）

**新增的功能**（Phase 1-3，Day 3-10）：
- 设备状态管理（心跳、错误日志）
- 任务队列（绘图、写字）
- 路径规划（SVG → G-code）
- MQTT 协议扩展

详见：
- [战略转型计划](docs/superpowers/plans/2026-06-09-lima-strategic-pivot-to-smart-devices.md)
- [LiMa 替换小智可行性分析](docs/superpowers/plans/2026-06-09-lima-replace-xiaozhi-feasibility.md)

---

## 许可证

MIT License

---

## 联系方式

- **开发者**: zhuguang-ZFG
- **GitHub**: https://github.com/zhuguang-ZFG/lima
- **Gitee**: https://gitee.com/zhuguang-zfg/lima

---

**LiMa —— 让 AI 硬件更智能！** 🤖✨
