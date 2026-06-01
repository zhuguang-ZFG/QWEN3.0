# LiMa — 运行状态

> 2026-06-01 · VPS `47.112.162.80` · 分支 `codex/free-web-ai-probe`
> 权威架构见 `docs/REQUEST_PIPELINE_AUTHORITY.md`
> 产品定义见 `docs/PRODUCT_DEFINITION.md`

## 全部里程碑

| # | 内容 | LOCAL_ONLY_BACKENDS |
|---|------|---------------------|
| M0 | 设计文档 `docs/DECOUPLE_FROM_LOCAL_HOST.md` | — |
| M1 | 清理 oldllm_* + 删除 local_* Ollama | 37→22 |
| M2 | SCNet Large VPS sidecar | 22→18 |
| M3 | Kimi VPS sidecar | 18→15 |
| M4 | LongCat VPS sidecar | 15→12 |
| M5 | MiMo VPS sidecar | 12→7 |
| M6 | 删除 DDG + deepseek_free | 7→0 |
| M7 | 清理残留 + ESP32 删除 (-647 行) | 0 |
| M8 | MiMo-Reasonix 深度分析 | 0 |
| M9 | LiMa Code CLI 初始化 + 烟雾测试 | 0 |
| M10 | 文档更新 + 13 个过期文档标记 | 0 |
| M11a | ModelScope 8 后端加入路由池 | 0 |
| M11b | 代码审查修复 (2 issues) | 0 |
| M11c | cache-first compaction 移植 (deepcode-cli@649eb34) | 0 |
| M11d | 完整 ContextManager 移植 (+412 行, deepcode-cli@182730d) | 0 |
| M11e | 部署验证 + 文档更新 | 0 |
| M11f | 代码审查修复 (D:/GIT 硬编码) | 0 |

## 部署状态

| 服务 | 端口 | 状态 |
|------|------|------|
| lima-router | 8080 | ✅ active |
| scnet-large-reverse | 4505 | ✅ healthy |
| kimi-proxy | 4504 | ✅ healthy |
| longcat-web-proxy | 4506 | ✅ healthy |
| mimo-proxy | 4507 | ✅ healthy |

## VPS 已清理

| 进程 | 原因 |
|------|------|
| `frps.service` | FRP 隧道不再需要 |
| `duckai` 容器 | DDG 后端已删除 |
| `proxy.py` (port 8000) | deepseek_free 已删除 |

## 关键指标

| 指标 | 值 |
|------|-----|
| `LOCAL_ONLY_BACKENDS` | **空集合** |
| `BACKEND_PORT_ENV` | **空字典** |
| `DISABLED_HOST_DEPENDENT_BACKENDS` | **空字典** |
| 后端总数 | **184**（全部云端化） |
| ModelScope 后端 | 8 个（ms_deepseek_v4/qwen35/kimi_k25/glm5 + code 变体） |
| VPS reverse sidecar | 5/5 active |
| net code removed | ~650 行 |

## LiMa Code CLI

| 指标 | 值 |
|------|-----|
| 版本 | v0.1.25 |
| 测试 | 507 tests, 498 pass, 2 fail (需本地服务), 7 skip |
| ContextManager | ✅ 已移植 (+412 行) |
| 端到端烟雾测试 | ✅ |

## 测试

| 套件 | 通过 | 说明 |
|------|------|------|
| LiMa pytest | 1972 | 85 预存失败 |
| LiMa Code CLI | 498 | 2 预存失败 |

## 不再依赖的本机服务

| 服务 | 状态 |
|------|------|
| Ollama (port 11434) | ❌ 已删除 |
| DuckAI (port 4500) | ❌ 已删除 |
| TheOldLLM 代理 (port 4502) | ❌ 已迁移到 CF Worker |
| FRP 隧道 | ❌ 已停用 |
