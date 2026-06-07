# LiMa — 当前任务计划

> Updated: 2026-06-07 · 权威状态见 `STATUS.md` + `AGENTS.md`

## 活跃优先级

### P0: 代码质量 — 大文件渐进拆分
- 权威 backlog: `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`
- 目标: 超 300 行文件拆分（目标 ≤300 行/文件, ≤50 行/函数）

### P1: 编码后端 — eval refresh + 路由硬化
- 重跑 eval 并刷新 scores/tiers
- `periodic_coding_eval.py`（`LIMA_PERIODIC_CODING_EVAL=1`）
- `health_tracker` + `probe_loop` 终端状态冷却

### P2: 系统瘦身与文档整理
- 清理过期文档、死代码、临时文件
- 精简根目录 Markdown 文件

## 已永久暂停
支付、公共注册、商业 billing、微信真机/机器人、ESP32 硬件依赖功能

## 验证命令

```powershell
.venv310\Scripts\python.exe -m pytest tests/ -q --tb=short
ruff check .
curl -sf http://127.0.0.1:8080/health
```
