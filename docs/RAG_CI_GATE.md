# RAG CI Gate

## 背景

离线 RAG fixture（`lima_core` / `lima_routing` / `lima_routing_prod`）已有 pytest 覆盖，但缺少独立 CI job 与统一入口。`server.py` 编排块已 ~181 行，CQ-014 文件大小目标已满足，本里程碑优先接 CI gate。

## 组件

| 文件 | 职责 |
|------|------|
| `context_pipeline/retrieval_eval_runner.py` | `DEFAULT_CI_FIXTURES`、`run_all_fixture_gates()` |
| `scripts/run_rag_eval_gate.py` | CLI 门禁（exit 0/1） |
| `.github/workflows/lima-ci.yml` | GitHub Actions：`pytest` + `rag-gate` job |
| `pytest.ini` | `rag_gate` marker |

## CI Fixtures

1. `tests/fixtures/retrieval_eval/lima_core.json` — sample_repo 语料
2. `tests/fixtures/retrieval_eval/lima_routing.json` — stub routing corpus + dual_layer
3. `tests/fixtures/retrieval_eval/lima_routing_prod.json` — 真实 repo 模块 `corpus_files`

## 本地用法

```bash
# 跑全部 CI fixture gate
python scripts/run_rag_eval_gate.py

# 单个 fixture
python scripts/run_rag_eval_gate.py --fixture tests/fixtures/retrieval_eval/lima_routing_prod.json

# pytest marker（与 CI rag-gate job 一致）
python -m pytest -q -m rag_gate
```

## GitHub Actions

`lima-ci.yml` 两个 job：

- **test** — 全量 `pytest -q`
- **rag-gate** — `run_rag_eval_gate.py` + `pytest -m rag_gate`

触发：`push` 到 `main`/`master`/`codex/**`，以及所有 `pull_request`。

## 验证

```bash
python scripts/run_rag_eval_gate.py
python -m pytest tests/test_retrieval_eval_fixture.py -q
```
