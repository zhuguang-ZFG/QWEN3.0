# LiMa Router + one-api 集成进度文档

> 更新时间: 2026-05-20 01:50
> 状态: one-api 基础设施就绪，渠道转发逐个调通中

---

## 一、系统架构

```
用户请求 (Cursor/Claude Code/Codex)
    ↓
server.py (:8088, OpenAI 兼容)
    ↓
smart_router.py (意图分类 <5ms, 74 后端, 21 供应商)
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

## 四、one-api 渠道状态 (23 个)

### 渠道配置
| # | 渠道名 | type | 模型数 | 分组 | 上游状态 |
|---|--------|------|--------|------|----------|
| 1 | zhipu | 8 (Custom) | 2 | default,trivial,general | ⚠️ 404 |
| 2 | siliconflow | 31 | 3 | default,trivial,general,thinking | ⚠️ 404 |
| 3 | baidu | 15 | 2 | default,trivial,general | ⚠️ 404 |
| 4 | volcengine | 40 | 1 | default,general,thinking | ⚠️ 待测 |
| 5 | aliyun | 17 | 2 | default,general,code | ⚠️ 待测 |
| 6 | tencent | 41 | 1 | default,general | ⚠️ 待测 |
| 7 | groq | 24 | 6 | default,trivial,code,general,thinking | ⚠️ 403 |
| 8 | mistral | 8 | 5 | default,code,general,thinking,vision | ⚠️ 待测 |
| 9 | mistral-codestral | 8 | 1 | default,code | ⚠️ timeout |
| 10 | nvidia | 8 | 6 | default,code,general,thinking,trivial | ⚠️ 待测 |
| 11 | github | 8 | 8 | default,code,general,thinking,vision | ⚠️ 待测 |
| 12 | google | 8 | 4 | default,general,thinking,vision | ⚠️ 待测 |
| 13 | cerebras | 8 | 3 | default,code,thinking | ⚠️ 待测 |
| 14 | openrouter | 8 | 10 | default,code,general,thinking | ⚠️ 待测 |
| 15 | longcat | 14 (Anthropic) | 4 | default,general,thinking,code | ⚠️ 待测 |
| 16 | deepseek | 36 | 2 | default,thinking,code | ⚠️ 待测 |
| 17 | chinamobile | 8 | 1 | default,general | ⚠️ 待测 |
| 18 | cloudflare | 25 | 2 | default,vision,general | ⚠️ 待测 |
| 19 | uncloseai-hermes | 8 | 1 | default,trivial,general | ⚠️ 待测 |
| 20 | uncloseai-qwen | 8 | 1 | default,code,general | ⚠️ 待测 |
| 21 | chat-ubi | 8 | 1 | default,trivial,general | ⚠️ 待测 |
| 22 | llm7 | 8 | 1 | default,general,code | ⚠️ 待测 |
| 23 | pollinations | 8 | 1 | default,general | ⚠️ 待测 |

### 已知问题（2026-05-20 02:10 诊断结果）

**诊断方法：** 直连 vs one-api 对比 + 容器日志分析

| 问题类型 | 渠道 | 原因 | 修复方向 |
|----------|------|------|----------|
| 转发格式不匹配 | zhipu, siliconflow, aliyun, volcengine, chinamobile, deepseek, longcat, nvidia, openrouter | one-api relay 格式与厂商期望不一致 | 需逐个调试 relay 行为 |
| API Key 过期/被封 | groq, cerebras | 直连也 403 | 需要重新获取 Key |
| GFW 被墙 | google, mistral, mistral-codestral | 云端无法直连 | 需配置 one-api 渠道级代理 |
| 认证格式特殊 | baidu (bce-v3), tencent (HunyuanSign) | 非标准 Bearer token | 需要对应 channel type |
| 非标准响应 | chat-ubi | 响应格式非标准 JSON | one-api 解析失败 |
| 模型加载中 | uncloseai-qwen | 冷启动 | 等待或预热 |
| 已通过 ✅ | pollinations | type=8 + 无需 auth | 正常工作 |

**关键发现：**
- one-api type=8 (Custom) 正确追加 `/chat/completions` ✓
- pollinations 成功证明 type=8 路径拼接正确 ✓
- 其他渠道失败是 relay 格式问题（非 URL 问题）
- 直连 fallback 完全正常工作 ✓

---

## 五、直连 fallback 验证结果

| 测试 | 意图 | 后端 | 延迟 | 结果 |
|------|------|------|------|------|
| "你好" | trivial | chat_ubi | 3062ms | ✅ |
| "写个快排" | trivial | chat_ubi | 5220ms | ✅ |
| "解释微服务架构" | architecture | mistral_large | 17720ms | ✅ |

直连 fallback 完全正常工作。

---

## 六、今日 Git 提交记录

```
312213d  路由 V2 — 纯规则分类 (<5ms)
dc73156  集成 LLM7 + Pollinations + tool_task
d691b48  零 Key 端点测试
c749914  集成 ch.at + DevToolBox Workers
bcb8136  GFW 反向代理支持
09b738d  threading import 修复
e7b1db3  DevToolBox 工具 API + Pollinations 图片生成
d570cb0  Codestral 提升优先级
b8fd595  系统性补齐各厂商模型 (46→63)
93ca98c  集成 6 个国内直连厂商 (63→74)
4905198  集成 one-api 渠道管理层
46fc978  one-api admin token + fallback 机制
```

---

## 七、下一步 TODO

1. [ ] 逐个调通 one-api 渠道（修复 auth/base_url/type）
2. [ ] 被墙渠道配置 HTTP 代理（one-api 支持 channel 级代理）
3. [ ] 验证 one-api 负载均衡和自动禁用功能
4. [ ] 额度追踪验证
5. [ ] 管理面板配置优化
