# LiMa 全项目审计报告与改善计划

> 审计日期：2026-06-22
> 审计范围：LiMa 服务、固件、Web 前端、小程序端、配置、文档、Docker/CI/CD
> 审计方法：6 个并行代理扫描 + 人工汇总

---

## 一、审计发现汇总

### 按严重程度分布

| 严重程度 | 数量 | 说明 |
|----------|------|------|
| 🔴 HIGH | 11 | 安全风险或硬规则违反，需优先修复 |
| 🟡 MEDIUM | 18 | 质量问题或潜在风险，需计划修复 |
| 🔵 LOW | 12 | 优化项，可排期处理 |

---

## 二、HIGH 级发现（11 项）

### H1. `except ImportError: pass` 静默降级（~50 处）

- **位置**：`routes/ops_metrics/collectors.py`（11 处）、其余分布在 `server_lifespan.py`、`context_pipeline/` 等模块
- **问题**：违反 AGENTS.md 硬规则 #1「禁止静默降级」；关键依赖缺失时无日志
- **修复**：每处改为 `except ImportError as exc: logger.warning(...)` 并说明影响

### H2. `except Exception: pass` 静默吞异常（7 处）

- **位置**：`conn.close()` 错误处理等
- **问题**：违反硬规则 #1
- **修复**：改为 `except Exception as exc: logger.debug("conn close failed: %s", exc)`

### H3. `pickle.loads` 不安全反序列化

- **位置**：`routing_loop/request_store.py:187`
- **问题**：pickle 反序列化可导致任意代码执行
- **修复**：替换为 JSON 序列化

### H4. 设备网关 WebSocket 先 accept 后认证

- **位置**：`routes/device_gateway_ws.py:101`
- **问题**：未认证连接先 accept，消耗资源（DoS 向量）
- **修复**：在 `accept()` 前校验 ticket/token，参考 `voice_pipeline_ws.py` 模式

### H5. admin.js XSS — `escJs` 在 HTML 属性上下文不安全

- **位置**：`data/chat/admin.js:52`（14 个调用点）
- **问题**：`escJs` 转义不适用于 HTML 属性注入
- **修复**：改用 `escapeHtml` 或 DOM API

### H6. 固件 `strcat` 无边界检查

- **位置**：`u1-grbl/.../ProcessSettings.cpp:331`、`Report.cpp:169,304,348`
- **问题**：缓冲区溢出风险
- **修复**：改用 `strncat` 或 C++ `std::string::append`

### H7. Dockerfile 无 non-root 用户

- **位置**：`Dockerfile`
- **问题**：容器以 root 运行
- **修复**：添加 `RUN useradd -r lima && USER lima`

### H8. docker-compose 端口绑定到 0.0.0.0

- **位置**：`docker-compose.yml` — `"8080:8080"`
- **问题**：Redis 等服务暴露到公网
- **修复**：改为 `"127.0.0.1:8080:8080"`

### H9. .env.example 仍有 ~100+ 环境变量未文档化

- **位置**：`.env.example`
- **问题**：`JDCLOUD_ROOT_PASSWORD`、`SUPABASE_SECRET`、`LIMA_XIAOZHI_LOGIN_CODE` 等敏感变量缺失
- **修复**：补充关键环境变量

### H10. `SEARXNG_URL` / `SEARXNG_BASE_URL` 命名不一致

- **位置**：代码读 `SEARXNG_URL`，`.env.example` 文档 `SEARXNG_BASE_URL`
- **问题**：功能静默使用硬编码默认值
- **修复**：统一变量名

### H11. Telegram 已退役但代码仍读 `LIMA_TELEGRAM_BOT_TOKEN`

- **位置**：`channel_retirement.py`（历史版本）
- **问题**：AGENTS.md 声明 Telegram 已退役，但代码仍引用
- **状态**：已修复 — 当前 `channel_retirement.py` 不再读取 Telegram token 或处理 webhook

---

## 三、MEDIUM 级发现（18 项）

### M1. 无 CORS 中间件
- **位置**：`server.py`
- **修复**：添加 `CORSMiddleware` 或文档说明 nginx 为唯一 CORS 执行点

### M2. 固件 `strcmp` 密码比较存在时序攻击风险
- **位置**：`u1-grbl/.../Authentication.cpp:28,33`
- **修复**：改为恒定时间比较

### M3. admin.js 无 CSRF token
- **位置**：`data/chat/admin.js:50`
- **修复**：admin API 已有 CSRF 检查（admin_auth），确认前端配合

### M4. 固件 `CreateHttp()` 返回值未检查（5 处）
- **位置**：`ota.cc:153,632`、`esp32_camera.cc:237`、`mcp_server.cc:209`、`assets.cc:436`
- **修复**：添加 null 检查

### M5. 文件 >300 行（2 个）
- **位置**：`browser_service.py`（400 行）、`routes/admin_ui/panels.py`（368 行）
- **修复**：拆分模块

### M6. 函数 >50 行（61 个）
- **最严重**：`run_all_discovery` 99 行、`deploy_unified.py::main` 82 行
- **修复**：按优先级逐步拆分

### M7. 8 个根模块无测试覆盖
- **模块**：`health_scoring.py`、`health_failure_classifier.py`、`coding_backend_scorer.py`、`context_compressor.py`、`sticky_session.py`、`think_plan_context.py`、`runtime_env.py`、`runtime_topology.py`

### M8. 18 个路由模块无测试引用
- **关键**：`chat_post_closeout.py`、`chat_stream.py`、`admin_backends.py`、`stream_handlers.py`

### M9. `routes/rate_limit_helper.py` 无单元测试
- **修复**：新增 `tests/test_rate_limit_helper.py`

### M10. 无端到端流水线集成测试
- **问题**：全请求流水线仅通过重度 mock 测试
- **修复**：新增轻量级集成测试

### M11. requirements_server.txt 混入开发依赖
- **问题**：`hypothesis`、`pyright`、`deptry`、`pytest-timeout` 在生产依赖中
- **修复**：拆分 `requirements_dev.txt`

### M12. docker-compose 无资源限制
- **修复**：添加 `mem_limit`、`cpus`、日志轮转配置

### M13. deploy.yml secrets 注入方式不安全
- **问题**：在 shell 脚本中使用 `${{ secrets.* }}`
- **修复**：改用 `env:` 映射

### M14. 部署脚本硬编码 VPS IP
- **修复**：改为环境变量配置

### M15. `tests/test_hypothesis_routing.py` 收集错误
- **问题**：`hypothesis` 包未安装
- **修复**：加入 dev 依赖或在 CI 中安装

### M16. AGENTS.md 引用不存在的文件
- **问题**：`docs/ROUTING_ENGINE_DESIGN.md`（已归档为 `docs/archive/ROUTING_ENGINE_DESIGN.md`）、`task_plan.md`（已归档为 `docs/archive/task_plan.md`）
- **修复**：已更新根文档与 `docs/README.md` 引用，并归档原文件

### M17. `.gitignore` 缺少敏感文件模式
- **修复**：添加 `*.sqlite`、`*.sqlite3`、`*.pem`、`*.key`、`.env.local`

### M18. `ruff.toml` lint 规则过窄
- **问题**：无安全规则（S 系列）、无导入检查
- **修复**：扩展规则集

---

## 四、LOW 级发现（12 项）

| # | 发现 | 位置 |
|---|------|------|
| L1 | `escapeAttr` 作用域 bug | `chat-web/chat-api.js:58` |
| L2 | `console.warn` 泄露 SSE 数据 | `chat-web/chat-api.js:150` |
| L3 | admin.js 18 处 `console.error` | `data/chat/admin.js` |
| L4 | API key 在 toast 中显示 | `data/chat/admin.js:168` |
| L5 | 图标按钮缺少 `aria-label` | `chat-web/index.html:230` |
| L6 | `strcpy` 竞态条件 | `emote_display.cc:152` |
| L7 | TODO/FIXME 残留（2 处） | stub provider |
| L8 | `import *`（1 文件） | 已有 `__all__` 缓解 |
| L9 | 无 Dependabot 配置 | `.github/dependabot.yml` |
| L10 | 过时文档（5+ 个） | `docs/superpowers/plans/` |
| L11 | 重复协议文档 | `docs/archive/xiaozhi_lima_protocol_alignment.md` vs `docs/archive/device_protocol_alignment.md`（均已归档） |
| L12 | SearXNG 无 profiles 分离 | `docker-compose.yml` |

---

## 五、改善计划

### 里程碑 E：安全加固（HIGH 优先）

| 编号 | 任务 | 文件 | 预估 |
|------|------|------|------|
| E1 | 替换 `pickle.loads` 为 JSON | `routing_loop/request_store.py` | 30min |
| E2 | WS 认证前置 | `routes/device_gateway_ws.py` | 1h |
| E3 | admin.js XSS 修复 | `data/chat/admin.js` | 1h |
| E4 | 固件 `strcat` → `strncat` | `ProcessSettings.cpp`, `Report.cpp` | 30min |
| E5 | Dockerfile non-root 用户 | `Dockerfile` | 15min |
| E6 | docker-compose 端口绑定 127.0.0.1 | `docker-compose.yml` | 15min |
| E7 | 移除 Telegram 残留引用 | `channel_retirement.py` | 15min |
| E8 | SEARXNG 变量名统一 | 代码 + `.env.example` | 15min |

### 里程碑 F：代码质量（MEDIUM 优先）

| 编号 | 任务 | 文件 | 预估 |
|------|------|------|------|
| F1 | 修复 ~50 处 `except ImportError: pass` | `routes/ops_metrics/collectors.py` 等 | 2h |
| F2 | 修复 7 处 `except Exception: pass` | 多文件 | 30min |
| F3 | 拆分 `browser_service.py`（400→<300） | `browser_service.py` | 1h |
| F4 | 拆分 `panels.py`（368→<300） | `routes/admin_ui/panels.py` | 1h |
| F5 | 拆分 `upload.py` 超长函数 | `routes/upload.py` | 已完成 |
| F6 | 补充 `.env.example` 缺失变量 | `.env.example` | 1h |
| F7 | `.gitignore` 补充敏感模式 | `.gitignore` | 15min |
| F8 | AGENTS.md 修正文件引用 | `AGENTS.md` | 15min |
| F9 | 拆分 `requirements_dev.txt` | `requirements_server.txt` | 15min |

### 里程碑 G：测试补全

| 编号 | 任务 | 预估 |
|------|------|------|
| G1 | 新增 `test_rate_limit_helper.py` | 30min |
| G2 | 为 `runtime_env.py`、`sticky_session.py` 补测试 | 1h |
| G3 | 为 `chat_post_closeout.py` 补测试 | 1h |
| G4 | 修复 `test_hypothesis_routing.py` 收集 | 15min |
| G5 | 新增轻量级端到端流水线测试 | 2h |

### 里程碑 H：部署与 CI 加固

| 编号 | 任务 | 预估 |
|------|------|------|
| H1 | docker-compose 资源限制 + 日志轮转 | 30min |
| H2 | deploy.yml secrets 注入修复 | 30min |
| H3 | 部署脚本去硬编码 IP | 30min |
| H4 | 新增 `.github/dependabot.yml` | 15min |
| H5 | SearXNG profiles 分离 | 15min |

### 里程碑 I：文档清理

| 编号 | 任务 | 预估 |
|------|------|------|
| I1 | 归档过时 `docs/superpowers/plans/` | 15min |
| I2 | 合并重复协议文档 | 15min |
| I3 | STATUS.md 测试计数修正 | 15min |
| I4 | 归档过时模型准入报告 | 15min |

### 里程碑 J：前端与固件清理（LOW）

| 编号 | 任务 | 预估 |
|------|------|------|
| J1 | `chat-api.js` escapeAttr 作用域修复 | 15min |
| J2 | admin.js console.error 清理 + key 显示修复 | 30min |
| J3 | 图标按钮 aria-label 补充 | 15min |
| J4 | 固件 `strcmp` → 恒定时间比较 | 15min |
| J5 | 固件 `CreateHttp()` null 检查 | 30min |

---

## 六、执行优先级

```
里程碑 E（安全 HIGH）→ F（质量 MEDIUM）→ G（测试）→ H（部署 CI）→ I（文档）→ J（前端固件 LOW）
```

**建议立即执行里程碑 E**（安全风险最高项），后续按 F→G→H→I→J 顺序推进。
