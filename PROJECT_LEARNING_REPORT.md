# LiMa 项目学习报告

> 生成时间：2026-06-11
> 项目状态：战略转型中（Phase 0）

## 项目概况

LiMa（力码）是深圳市动力巢科技有限公司的AI智能设备统一云端服务平台，正在从"个人编码助手后端"转型为"AI智能设备云端大脑"。

**核心使命**：让AI硬件更智能，为AI绘图机、写字机等智能设备提供云端大脑，让每个家庭拥有会画画、会写字的智能伙伴。

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.10 + FastAPI + uvicorn |
| HTTP客户端 | httpx（替代传统urllib） |
| 数据库 | SQLite（WAL + 外键） |
| 设备通信 | MQTT（设备 ↔ 云端双向） |
| 监控 | Prometheus + Grafana |
| 部署 | Docker Compose + 双VPS高可用 |

## 架构概览

```
客户端层（小程序/App/Web）
    ↓ HTTPS/WebSocket
API层（FastAPI routes/）
    ↓
业务层
    ├── AI Router（多模型调度）
    ├── Drawing Engine（SVG → G-code）
    ├── Writing Engine（字体渲染）
    └── Device Manager（设备管理）
    ↓
基础设施层（SQLite/Redis/MQTT/Prometheus）
    ↓ MQTT/WebSocket
设备层（ESP32绘图机/写字机）
```

## 核心模块

### 1. 路由引擎 (`routing_engine.py`)
- 五层统一路由：身份短路由 → 请求分类 → 场景分类 → 检索上下文注入 → 后端选择
- 支持170+ AI后端调度（OpenRouter、NVIDIA、Cloudflare、DeepSeek等）
- 基于健康状态、预算、质量评分的智能路由

### 2. 设备网关 (`device_gateway/`)
- 设备协议处理、任务投递、会话管理
- MQTT/WebSocket双向通信
- 支持多设备并发、Redis任务队列

### 3. 会话记忆 (`session_memory/`)
- 长期记忆、学习循环、脱敏、压缩
- 提示召回能力

### 4. 可观测性 (`observability/`)
- 结构化日志、Prometheus指标
- 后端遥测、关联ID、事件记录

## 当前状态

### 战略转型（2026-06-09启动）
- **已完成**：Phase 0文档更新、核心模块精简、代码质量审计
- **测试状态**：1886个测试通过，24个跳过
- **代码质量**：P0违规已修复（裸except: 2→0）
- **VPS状态**：容量感知部署，公共端点chat.donglicao.com/health=200

### 关键指标
| 指标 | 值 |
|------|-----|
| Python文件 | 5,103 |
| Python行数 | ~1,926,992 |
| 测试文件 | 201 |
| 路由文件 | 43文件 / ~6,680行 |
| 顶级目录 | 47 |

## 开发规范

### 代码质量红线
1. **禁止降级处理**：所有功能必须在正确配置下运行
2. **禁止裸except**：至少`logger.warning` + 类型名
3. **文件大小限制**：单文件≤300行，函数≤50行
4. **文档语言**：文档类产物必须使用中文

### 开发流程
```
1. 设计文档 (docs/*.md)
2. 本地编码
3. pytest测试
4. VPS部署 + health/smoke验证
5. 更新状态文档
6. git commit → push origin → push gitee
```

## 部署架构

- **主节点**：阿里云VPS（47.112.162.80）
- **备用节点**：京东云VPS（117.72.118.95）
- **公共端点**：chat.donglicao.com / api.donglicao.com
- **部署脚本**：`scripts/deploy_unified.py`

## 关键文档

| 文档 | 用途 |
|------|------|
| `AGENTS.md` | 项目开发规范 |
| `STATUS.md` | 项目状态 |
| `CLAUDE.md` | 开发规范摘要 |
| `docs/ARCHITECTURE.md` | 系统架构文档 |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | 请求处理流水线 |
| `task_plan.md` | 当前任务计划 |

## 下一步方向

1. **Phase 1**：核心设备服务上线
2. **Phase 2**：绘图/写字引擎完善
3. **Phase 3**：规模化（PostgreSQL, >500设备）

## 学习建议

1. **先读核心文档**：AGENTS.md、CLAUDE.md、STATUS.md
2. **理解架构**：docs/ARCHITECTURE.md、docs/REQUEST_PIPELINE_AUTHORITY.md
3. **查看代码**：从server.py入口开始，理解请求处理流程
4. **运行测试**：`python -m pytest --tb=short -q`验证项目状态
5. **查看部署**：scripts/deploy_unified.py了解部署流程

---

**报告总结**：LiMa是一个架构清晰、文档完善的AI智能设备云端服务平台，正处于从编码助手向智能设备服务转型的关键阶段。项目具有良好的代码质量规范和部署流程，适合深入学习和贡献。