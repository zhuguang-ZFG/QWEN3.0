# PE-D-1 SearXNG Runbook

> **Status:** Active | **Created:** 2026-05-26  
> **Scope:** dev-search / research **增强 tier**；**不改** chat 默认路由。

## 目标

自托管元搜索，为 `dev_search_docs` / `dev_search_error` 提供带 **source URL** 的 research grounding；默认关，限流时 fallback 到 TinyFish。

## 架构

```text
LiMa Code / MCP dev_search_*
  → search_gateway/dev_adapter.py
      → SearXNG (SEARXNG_ENABLED=1) — 优先
      → TinyFish — fallback
  → **不经过** routing_engine 热路径
```

## 本地 Docker 部署

镜像优先使用 **ghcr.io**（避免 Docker Hub 未认证 429）：

```powershell
cd D:\GIT\infra\searxng
docker compose up -d
curl -s "http://127.0.0.1:8081/search?q=test&format=json" | head
```

`settings.yml` 必须启用 JSON 格式，否则 API 返回 **403**：

```yaml
search:
  formats:
    - html
    - json
```

LiMa `.env`：

```env
SEARXNG_ENABLED=0
SEARXNG_BASE_URL=http://127.0.0.1:8081
SEARXNG_CACHE_TTL=300
SEARXNG_COOLDOWN_SEC=60
```

启用：

```env
SEARXNG_ENABLED=1
```

## Smoke

```powershell
python scripts/smoke_searxng_local.py
# SEARXNG_ENABLED=0 → smoke_ok (skip)
# SEARXNG_ENABLED=1 + docker up → 应返回带 searxng:engine 来源的结果
```

## VPS（可选）

与 Netdata 相同原则：**仅 loopback** 暴露（compose 已绑 `127.0.0.1:8081`）。

```powershell
python scripts/install_searxng_vps.py   # ghcr.io pull + compose up
python scripts/smoke_searxng_vps.py     # 8081 监听 + dev_adapter ok
```

**已知限制（2026-05-26 阿里云 VPS）：** 默认搜索引擎（Google/DDG 等）出站超时，SearXNG 返回空结果；`dev_adapter` 会自动 **fallback TinyFish**（`fallback_from=searxng`）。容器与 JSON API 仍可用，海外 VPS 或配置可用引擎后可得 `source: searxng:*`。

## 验收

- [ ] `SEARXNG_ENABLED=0` 时 dev-search 行为与改前一致（TinyFish）
- [ ] 启用后 research 结果含 `source: searxng:*`
- [ ] 429/不可达时 `_FallbackAdapter` 回退 TinyFish
- [ ] `progress.md` smoke 证据

## 参考

- [SearXNG docs](https://docs.searxng.org/)
- `search_gateway/searxng_adapter.py`
- `docs/superpowers/plans/2026-05-26-lima-productivity-enhancement.md` — PE-D-1
