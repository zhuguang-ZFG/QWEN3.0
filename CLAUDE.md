# LiMa 项目开发规范

## Superpowers 原则

### 1. 文档先行
- 任何非 trivial 改动，先写设计文档再编码
- 文档是设计决策的永久记录，代码会变但决策原因不该丢失
- 参考开源项目时记录具体借鉴了什么，为什么

### 2. 文件小而专注
- 单文件不超过 300 行（含注释）
- 每个文件只做一件事：路由/健康检查/会话管理 分别独立
- 函数不超过 50 行，超过就拆
- 不利于维护的大文件必须拆分

### 3. 本地验证再部署
- 本地完全实现 + 测试通过后，一次性替换服务器文件
- 不在生产服务器上边改边调
- 部署前备份，部署后验证

### 4. 永不破坏生产
- 服务器改动必须可回滚
- 新模块独立文件，不修改核心文件直到确认无误
- 端口冲突/进程残留等问题在部署脚本里处理

### 5. 参考业界最佳实践
- 每个设计决策都应有开源参考佐证
- clone 参考项目，分析源码，提取核心实现
- 不重复造轮子（如 pybreaker 代替自研熔断器）

### 6. 渐进式替换
- 新旧系统并行运行，逐步切流
- 保留旧代码直到新代码完全验证
- 灰度发布：先 1% 流量验证再全量

## 项目结构

```
/opt/lima-router/          ← 服务器部署目录
├── server.py              ← 主入口 (FastAPI)
├── smart_router.py        ← 旧路由引擎 (逐步替换)
├── router_v3.py           ← V3 三层路由核心
├── health_tracker.py      ← 健康追踪
├── sticky_session.py      ← 会话亲和
├── key_rotation.py        ← Key 轮转
├── path_proxy.py          ← 路径代理
└── key_pool.json          ← Key 池配置
```

## 开发流程

```
1. 设计文档 (docs/*.md)
2. 本地编码 (D:/GIT/*.py)
3. 本地测试 (pytest / curl)
4. Code Review
5. 一次性部署到服务器
6. 验证 (curl + 真实 IDE 测试)
7. 更新 STATUS.md
```

## 技术栈

- Python 3.10 + FastAPI + uvicorn
- httpx.AsyncClient (替换 urllib)
- pybreaker (熔断器)
- Redis (未来分布式状态)

## 关键设计文档

- `docs/ROUTING_V3_DESIGN.md` — 功能设计 (8模块)
- `docs/ROUTING_FIX_PLAN.md` — 实现方案 (14模块)
- `STATUS.md` — 项目状态追踪
