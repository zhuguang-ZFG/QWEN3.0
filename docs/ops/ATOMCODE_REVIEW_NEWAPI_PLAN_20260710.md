# AtomCode A2A 审查意见 — NewAPI Kimi 快路径方案

> **时间**：2026-07-10
> **通道**：A2A `http://127.0.0.1:4940`（AtomCode）via SSE `:41242`
> **脚本**：`scripts/a2a_atomcode_review_newapi_plan.js`
> **对象**：`docs/ops/NEWAPI_KIMI_IMPROVEMENT_PLAN_CN.md` + `apply_newapi_fast_tune.sh`

---

## 总体评价

质量很高的快路径方案，方向正确。CRYPTO / SESSION / SSE / Claude Header / Kimi base_url 收益风险比最高；SQLite 迁库后置合理。**建议执行，但须先处理 P0-1（阿里云 nginx 超时）。**

## 优点

1. 诊断准：Redis 已开缺 CRYPTO → 中继未完整生效
2. 范围克制：不做迁库 / :3001 / LiteLLM
3. 脚本有备份、幂等、smoke
4. 回滚路径真实
5. L0→L1→L2 分层清楚

## 问题摘要

| 级 | 项 | 状态 |
|----|-----|------|
| P0 | 阿里云 `proxy_read_timeout=300s` 会掐断 600s SSE | 已写入方案 Step A2 |
| P1 | 脚本 Python 硬编码路径 | 已修 `apply_newapi_fast_tune.sh` |
| P1 | 多 bak 时 `cp bak.*` 回滚失败 | 已改文档回滚命令 |
| P1 | Kimi 渠道未写明要填官方 key | 已改 Step B |
| P2 | 健康检查脚本偏弱 / cache 降级预案 / SQLite 写锁 | 已写入方案脚注 |

## 建议执行次序

1. Step A2：阿里云 nginx `proxy_read_timeout 600s` + reload
2. Step A：京东云 `apply_newapi_fast_tune.sh`
3. Step B/C/D：Web UI + Kimi CLI + 验收

完整原文见会话输出 / `_atomcode_newapi_plan_review.txt`（可删，含 JSON 包装）。
