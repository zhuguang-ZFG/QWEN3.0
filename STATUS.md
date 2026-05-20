# LiMa AI 项目状态

> 更新时间: 2026-05-20 08:30
> 阶段: V3 路由重设计完成文档，准备编码实现

---

## 本次会话完成 (2026-05-20)

### V3 路由重设计（文档完成，待编码）

| 模块 | 文档 | 编码 |
|------|------|------|
| IDE 识别 (指纹+UA) | ✅ | ⚠️ 已部署但有问题 |
| Skills 注入 | ✅ | ⚠️ 已部署但路由问题导致未生效 |
| Anthropic API 兼容层 | ✅ | ⚠️ 端点已有，格式转换待完善 |
| 三层路由架构 | ✅ | ❌ 待实现 |
| 后端池 + 健康感知 | ✅ | ❌ 待实现 |
| 被动追踪 + 主动探活 | ✅ | ❌ 待实现 |
| 删除预设直答 | ✅ | ❌ 待实现 |
| 并发支持 (httpx async) | ✅ | ❌ 待实现 |
| 多 IDE 支持 (Cursor/Codex/Cline/Aider) | ✅ | ❌ 待实现 |
| 百万级分布式架构 | ✅ | ❌ 长期目标 |

### 已部署到服务器（有问题待修复）

| 改动 | 状态 | 问题 |
|------|------|------|
| Phase 1: IDE 识别 + Skills 注入 | 已部署 | 路由仍走 chat_ubi |
| User-Agent 检测 Claude Code | 已部署 | Claude Code UA 未确认 |
| Anthropic 格式强制走 longcat_chat | 已部署 | 预设直答仍会误触发 |
| 防火墙开放 8080 端口 | ✅ | 安全组已开 |

### 设计文档

| 文档 | 内容 |
|------|------|
| docs/ROUTING_V3_DESIGN.md | 8模块: IDE识别/双层路由/代码路由/Skills/动态排名/代码增强/Anthropic兼容/多IDE |
| docs/ROUTING_FIX_PLAN.md | 14模块: 三层架构/后端池/健康检查/熔断器/并发/百万级/源码分析 |

### 参考项目已 clone

| 项目 | 路径 | 参考点 |
|------|------|--------|
| LiteLLM | D:/GIT/litellm-ref | 冷却期TTL/延迟路由/fallback |
| RouteLLM | D:/GIT/routellm-ref | 强弱分层/阈值校准 |
| Portkey | D:/GIT/portkey-ref | 条件路由/Hooks/重试 |

---

## 之前已完成

### 5 个多模态功能 (Sprint 1-5)

| Sprint | 功能 | 状态 |
|--------|------|------|
| 1 | 深度思考模式 | ✅ |
| 2 | AI 生图 | ✅ |
| 3 | 拍题答疑 (Vision) | ✅ |
| 4 | 语音实时交互 | ✅ |
| 5 | 动画头像视频通话 | ✅ |

### 平台部署

| 服务 | 域名/端口 | 状态 |
|------|-----------|------|
| 品牌官网 | www.donglicao.com | ✅ |
| API 控制台 | api.donglicao.com | ✅ (new-api) |
| LiMa 路由 API | 47.112.162.80:8080 | ✅ (外网可访问) |
| one-api | 47.112.162.80:3001 | ✅ (16渠道) |
| 语音网关 | systemd lima-voice (8091) | ✅ |
| 监控 | cron health_check.sh | ✅ |

### 代码改动 (核心文件)

| 文件 | 改动内容 |
|------|----------|
| server.py | +300 行 (thinking/vision/image/streaming/context) |
| smart_router.py | +200 行 (thinking/vision/image detection) |
| voice_gateway.py | 新建 (WebSocket + STT + TTS) |
| lima-enhance.js | 新建 (chat UI 工具栏注入) |
| voice-call.html | 新建 (视频通话页面) |
| fragments/*.md | 新建 (可组合 Prompt 片段) |
| docs/ | 10+ 份设计文档 |

### 文档

| 文档 | 状态 |
|------|------|
| docs/MULTIMODAL_FEATURES_PLAN.md | ✅ 含语音+视频通话 |
| docs/TECHNICAL_ARCHITECTURE.md | ✅ |
| docs/CONTEXT_ENGINEERING.md | ✅ |
| docs/ANTI_FORGETTING_STRATEGY.md | ✅ |
| docs/ROUND15_TRAINING_STRATEGY.md | ✅ |
| docs/ROUTER_CLASSIFIER_V2.md | ✅ |
| docs/PLATFORM_UPGRADE.md | ✅ |
| docs/PAYMENT_DESIGN.md | ✅ |
| docs/BRANDING_UNIFICATION.md | ✅ |
| docs/CLAUDE_CODE_BREAKTHROUGH.md | ✅ |
| docs/copilot-chat-context-construction.md | ✅ |

---

## 待修复（高优先级）

| 问题 | 根因 | 状态 |
|------|------|------|
| 预设直答误触发 | _try_instant_reply 正则匹配 | ❌ 待删除 |
| IDE 请求路由到 chat_ubi | 单一 fallback 链 + 多后端熔断 | ❌ 待重设计 |
| 多后端 403/401 | Groq/Silicon/Mistral key 或限流 | ⚠️ 需排查 |
| Claude Code 无上下文 | OpenAI 模式不发 system prompt | ⚠️ 需 Anthropic 兼容层 |
| 并发瓶颈 ~40 QPS | urllib 同步阻塞 + 线程池 | ❌ 待换 httpx async |

## 待修复（中优先级）

| 问题 | 状态 |
|------|------|
| chat 上下文丢失 | 🔧 修复中 |
| 模型身份泄露 | ⚠️ 已加固 clean_patterns |
| UI 工具栏不显示 | ⏸️ 需清缓存 |

---

## 重启后需要手动执行

### 云端服务 (auto-start via systemd)
```bash
systemctl status lima-router  # 端口 8090，开机自启
systemctl status lima-voice   # 端口 8091，开机自启
podman ps | grep -E "new-api|nextchat"  # 容器自启
```

### 本地服务
```bash
cd D:/GIT && python server.py          # 本地路由 (如需要)
D:/GIT/frp/frpc.exe -c D:/GIT/frp/frpc.toml  # frp 隧道 (如需要)
```

### 启动 R15 训练
```bash
cd D:/GIT && D:/GIT/venv/Scripts/python.exe prepare_r15_data.py  # 先准备数据
cd D:/GIT && D:/GIT/venv/Scripts/python.exe train_r15.py         # 启动训练
```

---

## 关键路径

| 文件 | 位置 |
|------|------|
| 云端路由 | /opt/lima-router/server.py |
| 云端路由引擎 | /opt/lima-router/smart_router.py |
| 语音网关 | /opt/lima-voice/voice_gateway.py |
| new-api 数据库 | /opt/new-api/one-api.db |
| Nginx 配置 | /etc/nginx/conf.d/donglicao.conf (api) |
| Nginx 配置 | /etc/nginx/conf.d/chat.donglicao.com.conf (chat) |
| 官网 | /www/wwwroot/donglicao-site/ |
| 日志 | journalctl -u lima-router |
| GitHub | github.com/zhuguang-ZFG/QWEN3.0 (master) |
