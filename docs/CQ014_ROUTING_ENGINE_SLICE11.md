# CQ-014 Routing Engine Slice 11

## 背景

`routing_engine.py` 约 447 行，五层逻辑可独立测试。

## 拆分

| 文件 | 层 | 导出 |
|------|-----|------|
| `routing_classifier.py` | classify / classify_scenario | `classify`, `classify_scenario` |
| `routing_selector.py` | select / rank | `select` |
| `routing_executor.py` | execute / fallback | `execute`, `extract_error_code` |
| `routing_engine.py` | 编排 + RouteResult + route() | 全部 re-export |

## 兼容

外部仍 `import routing_engine`；`classify`、`select`、`execute` 等符号不变。

## 验证

```bash
pytest test_routing_engine.py tests/test_routing_engine.py -q
```
