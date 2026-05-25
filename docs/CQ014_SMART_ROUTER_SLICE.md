# CQ-014 Smart Router Slices 6–7

## 目标

将 `smart_router.py` 中可独立测试的子模块抽出，保持对外 API 不变。

## 拆分结果

| 模块 | 文件 | 职责 |
|------|------|------|
| 熔断器 | `router_circuit_breaker.py` | `cb_allow` / `cb_record` / `cb_status` |
| 意图检测 | `router_intent.py` | `detect_thinking_intent` / `get_thinking_backend` |
| 分类器栈 | `router_classifier.py` | `RULES` / `rule_classify` / `signal_classify` / `analyze` |
| Prompt 片段 | `router_prompt.py` | `assemble_prompt` / `SYS` |
| 同步 HTTP | `router_http.py` | `call_api` / `call_api_stream` / SCNet / cf_vision |
| 文生图意图 | `router_image.py` | `detect_image_intent` |
| Vision 格式 | `vision_handler.py` | `detect_vision_request` / `convert_openai_vision_to_anthropic` |
| 响应清洗 | `response_cleaner.py` | `clean_response` |

`smart_router.py` 继续 re-export 上述符号（~228 行），现有调用方无需改动。

## 验证

```bash
pytest tests/test_router_*.py tests/test_vision_routing.py tests/test_retrieval_eval_fixture.py -q
pytest -q
```

## 后续 slice

- `http_caller.py` 进一步拆分
- `health_tracker.py` 拆分
- 可选：彻底移除 smart_router 中未使用的 local Qwen router 模型路径
