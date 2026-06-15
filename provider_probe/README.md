# provider_probe

> 更新：2026-06-15
> 层级：**Cold**（离线实验流水线）
> 权威说明：[`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](../docs/CODEBASE_SUBSYSTEM_TIER_CN.md) §6

## 用途

新 AI 提供商发现、网页/平台监控、浏览器逆向、连通性验证、后端常量**草稿**生成。产出须经人工 review 后合入 `backends_registry.py`。

## 与运行时探活的区别

| 组件 | 层级 | 说明 |
|------|------|------|
| `probe_loop.py`（仓库根） | Warm | `server_lifespan` 启动的后端健康探活 |
| **`provider_probe/` 包** | Cold | 不得被 `server.py` / 路由注册默认挂载 |

## 运行方式

手动脚本或 JDCloud 探测节点；典型入口见 `browser_service.py` 与各 `discovery/`、`verify/` 子模块。无生产 API 依赖本包。
