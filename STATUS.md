# LiMa Code — 运行状态

> 更新: 2026-06-01 · VPS: `47.112.162.80` · 分支: `codex/free-web-ai-probe`

## M1-M9 里程碑完成状态

| # | 内容 | 状态 | LOCAL_ONLY_BACKENDS |
|---|------|------|---------------------|
| M0 | 设计文档 | ✅ | — |
| M1 | 清理 oldllm_* + 删除 local_* Ollama 模型 | ✅ | 37→22 |
| M2 | 启用 SCNet Large VPS sidecar | ✅ | 22→18 |
| M3 | Kimi VPS sidecar | ✅ | 18→15 |
| M4 | LongCat VPS sidecar | ✅ | 15→12 |
| M5 | MiMo VPS sidecar | ✅ | 12→7 |
| M6 | 删除 DDG + deepseek_free | ✅ | 7→0 |
| M7 | 清理残留 + ESP32 删除 | ✅ | -647 行 |
| M8 | MiMo-Reasonix 深度分析 | ✅ | 参考文档 |
| M9 | LiMa Code CLI 初始化 + 烟雾测试 | ✅ | 端到端通过 |
| M10 | 文档更新 + 过期标记 | ✅ | 13 个过期文档已标记 |
| M11a | ModelScope 8 后端加入路由池 | ✅ | VPS 已验证 |
| M11b | 代码审查修复 | ✅ | 2 minor 问题已修 |
| M11c | cache-first compaction 移植 | ✅ | deepcode-cli@649eb34 |
| M11d | 完整 ContextManager 移植 | ✅ | +412 行, deepcode-cli@182730d |

## 部署状态

| 服务 | 端口 | 状态 |
|------|------|------|
| lima-router | 8080 | ✅ active (184 backends, 全部云端化) |
| scnet-large-reverse | 4505 | ✅ ready_protocol_adapter |
| kimi-proxy | 4504 | ✅ ready_proxy_shell |
| longcat-web-proxy | 4506 | ✅ ready_proxy_shell |
| mimo-proxy | 4507 | ✅ ready_proxy_shell |
| keepalive cron | — | ✅ 每 30 分钟 |

## 关键指标

| 指标 | 之前 | 之后 |
|------|------|------|
| `LOCAL_ONLY_BACKENDS` | 37 | **0** |
| `BACKEND_PORT_ENV` (FRP 隧道) | 14 条目 | **0** |
| `DISABLED_HOST_DEPENDENT_BACKENDS` | 37 后端 | **0** |
| 总后端数 | ~170 | **184**（全部云端化） |
| 净删代码 | — | **~600 行** |
| runtime_topology.py | 112 行 | **44 行** |
| eval_topology.py | 122 行 | **49 行** |
| oldllm_diag.py | 322 行 | **231 行** |

## VPS 清理 (M11)

| 进程 | 结果 |
|------|------|
| `frps.service` (FRP 隧道) | ✅ 已停止+禁用 |
| `duckai` 容器 | ✅ 已停止+删除 |
| `proxy.py` port 8000 | ✅ 已 kill |

## CLI 状态 (LiMa Code)

| 指标 | 值 |
|------|-----|
| 版本 | lima-code v0.1.24 |
| 测试 | 445 tests, 436 pass, 2 fail (需本地服务), 7 skip |
| 配置 | `.lima-code/settings.json` → LiMa VPS |
| 烟雾测试 | ✅ headless prompt → scnet_ds_flash → 正确输出 |
| 工作流 | `/lima plan|test|review|ship|task|work` |

## 不再依赖的本机服务

| 服务 | 状态 |
|------|------|
| Ollama (port 11434) | ❌ 已删除 |
| DuckAI (port 4500) | ❌ 已删除 |
| TheOldLLM 代理 (port 4502) | ❌ 已迁移到 CF Worker |
| g4f (port 4503) | ❌ 不再需要 |
| FRP 隧道 (port 8088) | ❌ 不再需要 |
| Windows lima-startup.bat | ⚠️ 待手动停用 |
