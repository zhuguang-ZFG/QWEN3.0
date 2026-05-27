# Production Retrieval Wiring

## 背景

离线 eval fixture `lima_routing_prod.json` 已验证 prod 语料可检索；本里程碑将同一语料列表接入 `retrieval_injection` 生产路径。

## 组件

| 文件 | 职责 |
|------|------|
| `context_pipeline/retrieval_corpus.py` | `PRODUCTION_CORPUS_FILES` 与路径解析 |
| `context_pipeline/production_index.py` | 单例 `InMemoryTokenIndex` + `search_production_corpus()` |
| `context_pipeline/code_scanner.py` | `scan_files()` + prod corpus 优先建图 |
| `context_pipeline/retrieval_injection.py` | vector 层改用 prod index 搜索 |

## 语料列表

与 `tests/fixtures/retrieval_eval/lima_routing_prod.json` 的 `corpus_files` 对齐（9 个 routing 核心模块）。

## 验证

```bash
python -m pytest tests/test_production_retrieval.py tests/test_retrieval_injection.py -q
python scripts/run_rag_eval_gate.py
python scripts/run_ci_local.py
python scripts/deploy_prod_retrieval.py
python scripts/vps_run_retrieval_smoke.py
```

### VPS smoke（2026-05-25）

- Backup: `/opt/lima-router/backups/prod-retrieval-20260525_143719/runtime-before.tgz`
- Token: `prod_retrieval_trace_ok`
- Evidence: chat HTTP 200; admin retrieval trace `injected_chars=380`; entities `health_tracker.py`, `routing_engine.py`
