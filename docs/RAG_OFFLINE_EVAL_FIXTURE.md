# RAG 离线 Eval Fixture

## 背景

LiMa 检索链路已有 `context_pipeline/retrieval_eval.py` 指标层和 `local_retrieval/eval_bridge.py` 索引桥接，但缺少可回归的固定语料 + 查询集。

参考 GCP generative-ai RAG grounding 评测方法论（见 `docs/GCP_GENERATIVE_AI_RESEARCH.md`），采用 **离线 fixture + 阈值 gate**，不依赖网络或外部 evaluator。

## 组件

| 文件 | 职责 |
|------|------|
| `tests/fixtures/retrieval_eval/lima_core.json` | 固定语料路径 + 查询 + 期望命中 + gate 阈值 |
| `context_pipeline/retrieval_eval_runner.py` | 加载 fixture、建索引、跑指标、gate 判定 |
| `tests/test_retrieval_eval_fixture.py` | 离线回归测试 |

## Fixture 格式

```json
{
  "name": "lima_core",
  "corpus_root": "tests/fixtures/sample_repo",
  "top_k": 5,
  "match_by": "basename",
  "thresholds": {
    "min_hit_rate": 0.75,
    "min_mean_recall": 0.5,
    "min_mean_mrr": 0.25
  },
  "queries": [
    {
      "query": "Calculator add subtract value class",
      "expected_paths": ["module_a.py"],
      "description": "Find Calculator class in module_a"
    }
  ]
}
```

- `match_by`: `basename`（按文件名匹配）或 `chunk_id`（精确 chunk）
- `thresholds`: 低于任一阈值则 gate FAIL

## 指标

复用 `retrieval_eval.py`：

- recall
- precision@k
- hit_rate
- MRR

## 用法

```python
from context_pipeline.retrieval_eval_runner import run_fixture_eval, format_fixture_report

spec, summary, passed, failures = run_fixture_eval("tests/fixtures/retrieval_eval/lima_core.json")
print(format_fixture_report(spec, summary, passed, failures))
```

## 扩展

1. `tests/fixtures/retrieval_eval/lima_routing.json` — LiMa 路由语料 + `graph_relations` + `eval_mode: dual_layer`
2. `tests/fixtures/routing_corpus/` — 路由模块 stub 语料
3. CI 中将 `test_retrieval_eval_fixture.py` 作为 RAG 回归门禁

### graph_relations 与 dual_layer

```json
{
  "eval_mode": "dual_layer",
  "graph_relations": [
    {"source": "routing_engine.py", "target": "http_caller.py", "relation_type": "imports"}
  ]
}
```

`retrieval_eval_runner.evaluate_fixture()` 在 `dual_layer` 模式下调用 `graph_retrieval.dual_layer_search` 合并 vector + graph 结果。

### 生产语料（repo 文件列表）

`lima_routing_prod.json` 通过 `corpus_files` 指向仓库内真实模块，避免 walk 整个 repo 引入噪声：

```json
{
  "name": "lima_routing_prod",
  "corpus_root": ".",
  "corpus_files": [
    "routing_engine.py",
    "routing_classifier.py",
    "http_caller.py",
    "health_tracker.py"
  ],
  "eval_mode": "dual_layer",
  "graph_relations": [...]
}
```

`resolve_corpus_files()` 将相对路径解析为 repo 根目录下的绝对路径；仅索引存在的文件。

## 验证

```bash
pytest tests/test_retrieval_eval_fixture.py -q
```
