# LiMa AI 项目状态

> 更新时间: 2026-05-19 03:18
> 会话时长: ~8 小时
> 阶段: 5 个多模态 Sprint 完成，部分问题待修复

---

## 已完成

### 5 个多模态功能 (Sprint 1-5)

| Sprint | 功能 | 状态 | 验证 |
|--------|------|------|------|
| 1 | 深度思考模式 | ✅ | thinking 参数路由到 DeepSeek R1 / LongCat Thinking |
| 2 | AI 生图 | ✅ | Pollinations.ai 免费接口 + /v1/images/generations |
| 3 | 拍题答疑 (Vision) | ✅ | 图片检测 + OpenAI→Anthropic 格式转换 |
| 4 | 语音实时交互 | ✅ | voice_gateway.py (WebSocket + Whisper + Edge-TTS) |
| 5 | 动画头像视频通话 | ✅ | voice-call.html (SVG 口型同步) |

### 平台部署

| 服务 | 域名 | 状态 |
|------|------|------|
| 品牌官网 | www.donglicao.com | ✅ |
| API 控制台 | api.donglicao.com | ✅ (new-api) |
| 免费聊天 | chat.donglicao.com | ⚠️ 工具栏待验证 |
| 云端路由 | systemd lima-router (8090) | ✅ |
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

## 待修复

### 高优先级

| 问题 | 根因 | 状态 |
|------|------|------|
| chat 上下文丢失 | route() 只传最后一条消息给后端 | 🔧 修复中 |
| chat 偶尔空响应 | streaming 路径对非即时回复处理不完善 | 🔧 修复中 |
| UI 工具栏不显示 | 浏览器 Service Worker 缓存旧页面 | ⏸️ 需用户在关闭窗口前先清缓存 (F12→Application→Service Workers→Unregister→Ctrl+Shift+R) |
| 模型身份泄露 | 某些后端忽略 system prompt，暴露真实模型名 | ⚠️ 已加固 clean_patterns |

### 中优先级

| 问题 | 状态 |
|------|------|
| 模型名 "redcode-v1.2" 残留 | ⚠️ clean_response 已处理 |
| GitHub/NextChat 品牌残留 | ⚠️ CSS sub_filter 注入，需清缓存 |
| one-api 旧二进制未完全删除 | 可清理 |

### 低优先级

| 问题 | 状态 |
|------|------|
| R15 训练未启动 | 数据已准备 (2082条) |
| 支付集成 | 文档完成，代码未启动 |
| 充值付费 | 文档完成，代码未启动 |

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
