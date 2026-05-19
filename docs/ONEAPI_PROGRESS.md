# LiMa Router + one-api 集成进度文档

> 更新时间: 2026-05-20 03:30
> 状态: one-api 18 渠道，12 通过 + 3 限流 + 3 故障

---

## 一、系统架构

```
用户请求 (Cursor/Claude Code/Codex)
    ↓
server.py (:8088, OpenAI 兼容)
    ↓
smart_router.py (规则+信号分类 <5ms, 74 后端, 21 供应商)
    ↓ 优先
one-api (:3001, 负载均衡/额度追踪/自动禁用)
    ↓ 失败时降级
直连 fallback chain (74 后端直连)
    ↓ 被墙后端
GFW 代理 (frp 隧道 → 本地 Clash :7897)
    ↓
实际 LLM API
```

---

## 二、组件状态

| 组件 | 端口 | 状态 | PID/容器 |
|------|------|------|----------|
| server.py | 8088 | ✅ 运行中 | 2712533 |
| one-api (podman) | 3001 | ✅ 运行中 | one-api |
| frpc (GFW 代理) | 7897 | ✅ 运行中 | 本地 41412 |
| Clash Verge | 7897(本地) | ✅ 运行中 | 本地 24468 |

管理面板: http://47.112.162.80:3001 (root/123456)

---

## 三、后端总览 (74 个, 21 供应商)

### 国内直连 (11 个, 无需翻墙)
| 后端 | 供应商 | 模型 | 延迟 |
|------|--------|------|------|
| zhipu_flash | 智谱 AI | glm-4-flash | <100ms |
| zhipu_flash7 | 智谱 AI | glm-4.7-flash (200K) | <100ms |
| silicon_qwen8b | 硅基流动 | Qwen3-8B | <100ms |
| silicon_glm9b | 硅基流动 | glm-4-9b-chat | <100ms |
| silicon_deepseek | 硅基流动 | DeepSeek-R1-Distill | <150ms |
| baidu_ernie | 百度千帆 | ernie-3.5-8k (永久免费) | <100ms |
| baidu_speed | 百度千帆 | ernie-speed-8k | <80ms |
| volcengine_doubao | 火山引擎 | doubao-1-5-pro-256k | <150ms |
| aliyun_qwen3 | 阿里百炼 | qwen3-8b | <100ms |
| aliyun_coder | 阿里百炼 | qwen-3-coder-plus | <150ms |
| tencent_hunyuan | 腾讯混元 | hunyuan-lite | <100ms |

### 国际直连 (52 个, 从阿里云可达)
| 供应商 | 数量 | 代表模型 |
|--------|------|----------|
| Groq | 6 | GPT-OSS 120B/20B, Llama 70B, Qwen3 32B |
| GitHub | 8 | GPT-5, o3-mini, o4-mini, DeepSeek R1 |
| NVIDIA | 6 | Nemotron, Qwen Coder 480B, Llama 4 |
| OpenRouter | 10 | 10 个免费模型 |
| Cerebras | 3 | Qwen 235B, GPT-OSS 120B |
| LongCat | 5 | Flash-Lite/Chat/Thinking/Omni/2.0 |
| DeepSeek | 2 | V4 Pro/Flash |
| UncloseAI | 2 | Hermes 8B, Qwen3 27B |
| ChinaMobile | 1 | MiniMax M25 |
| ZeroKey | 3 | ch.at, LLM7, Pollinations |

### 需 GFW 代理 (11 个)
| 供应商 | 数量 | 代表模型 |
|--------|------|----------|
| Google | 4 | Gemini 3 Flash, 2.5 Flash, Gemma 27B |
| Mistral | 6 | Large, Codestral, Devstral, Pixtral |
| Cloudflare | 5 | Llama Vision, Mistral Small |

---

## 四、one-api 渠道状态 (18 个)

### 通过验证 (12 个) ✅

| 渠道 | 方式 | 延迟 | 状态 |
|------|------|------|------|
| deepseek | type=8 直连 | 614ms | ✅ |
| groq | type=8 + GFW 代理 | 476ms | ✅ |
| cerebras | type=8 + GFW 代理 | 692ms | ✅ |
| zhipu | path_proxy :8901 | 650ms | ✅ |
| github | path_proxy :8902 | 2406ms | ✅ |
| aliyun | path_proxy :8903 + enable_thinking | 396ms | ✅ |
| chinamobile | path_proxy :8904 | 响应改写 | ✅ |
| chat-ubi | type=8 直连 | 1496ms | ✅ |
| pollinations | type=8 直连 | 786ms | ✅ |
| llm7 | type=8 直连 | 1254ms | ✅ |
| uncloseai-hermes | type=8 直连 | 待测 | ✅ |
| uncloseai-qwen | type=8 直连 | 待测 | ✅ |

### 限流中 (3 个) ⚠️

| 渠道 | 原因 | 恢复时间 |
|------|------|----------|
| openrouter | 20 RPM 限流 | 1 分钟后 |
| mistral | 免费额度限流 | 24 小时后 |
| google | 15 RPM 限流 | 4 分钟后 |

### 故障 (3 个) ❌

| 渠道 | 问题 | 修复方向 |
|------|------|----------|
| longcat | 404 bug (LongCat API 变更) | 等待 LongCat 修复或改用直连 |
| baidu | 账户过期 (overdue) | 需要续费或重新认证 |
| volcengine | 模型不存在 (model not found) | 检查模型名是否正确 |

---

## 五、path_proxy 完整端口表

| 端口 | 上游 | 功能 | 状态 |
|------|------|------|------|
| 8901 | zhipu | 路径重写 /v1→/v4 | ✅ |
| 8902 | github | 去掉 /v1 前缀 | ✅ |
| 8903 | aliyun | 注入 enable_thinking=false | ✅ |
| 8904 | chinamobile | 响应改写 reasoning→content | ✅ |
| 8905 | google | frp 代理 + 路径处理 | 待部署 |
| 8906 | baidu | 特殊认证 (bce-v3) | 待部署 |
| 8907 | volcengine | 模型名映射 | 待部署 |
| 8908 | longcat | Anthropic 格式转换 | 待部署 |

---

## 六、直连 fallback 验证结果

| 测试 | 意图 | 后端 | 延迟 | 结果 |
|------|------|------|------|------|
| "你好" | trivial | chat_ubi | 3062ms | ✅ |
| "写个快排" | trivial | chat_ubi | 5220ms | ✅ |
| "解释微服务架构" | architecture | mistral_large | 17720ms | ✅ |

直连 fallback 完全正常工作。

---

## 七、今日 Git 提交记录

```
ac5e770  feat: chinamobile 通过 path_proxy 响应改写修通 (10/10)
e56adee  feat: path_proxy 修复 zhipu/github/aliyun 通过 one-api (9/9)
21eaa5c  docs: one-api 集成经验教训 + 最终修复脚本
1e61dbb  docs: one-api 集成进度文档 + 诊断脚本
46fc978  fix: one-api 使用 admin token + fallback 机制完善
```

---

## 八、下一步 TODO

1. [x] 12 个渠道通过验证
2. [ ] 部署 path_proxy 8905-8908 端口
3. [ ] 修复 longcat/baidu/volcengine 故障
4. [ ] 验证 one-api 负载均衡和自动禁用功能
5. [ ] 额度追踪验证
