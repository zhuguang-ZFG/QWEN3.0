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

1. 新增 fixture JSON（如 `lima_routing.json` 指向真实路由模块语料）
2. 可选 `graph_relations` 字段对接 `graph_retrieval.dual_layer_search`
3. CI 中将 `test_retrieval_eval_fixture.py` 作为 RAG 回归门禁

## 验证

```bash
pytest tests/test_retrieval_eval_fixture.py -q
```
