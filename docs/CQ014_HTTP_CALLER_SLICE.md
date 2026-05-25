# CQ-014 HTTP Caller Slice 8

## 目标

将 `http_caller.py` 拆分为可独立测试的子模块，保持对外 API 与 patch 点不变。

## 拆分结果

| 模块 | 文件 | 职责 |
|------|------|------|
| 错误类型 | `http_errors.py` | `BackendError` / status / observability emit |
| 请求构建 | `http_request_builder.py` | client factory / headers / body / key pool |
| 响应解析 | `http_response.py` | `_extract_answer` / `_extract_usage` / `_parse_sse_chunk` |
| 流式 | `http_stream.py` | `call_api_stream` / `call_api_stream_async` |
| 入口 | `http_caller.py` | sync/async call + raw + probe + re-export |

`http_caller.py` 继续 re-export 私有符号（`_build_client` 等），现有测试 patch 点无需改动。

## 验证

```bash
pytest test_http_caller.py tests/test_http_caller_concurrency.py -q
pytest -q
```

## 后续

- `health_tracker.py` 拆分
- 可选：将 sync/async call 进一步收到 `http_sync.py` / `http_async.py`
