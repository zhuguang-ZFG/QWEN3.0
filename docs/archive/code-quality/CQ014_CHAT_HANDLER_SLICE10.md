# CQ-014 Chat Handler Slice 10

## 目标

将 `routes/chat_handler.py` 压到 300 行以内，提取 preflight 与 post-closeout。

## 拆分结果

| 模块 | 文件 | 职责 |
|------|------|------|
| Preflight | `routes/chat_preflight.py` | guardrails、prompt context、token budget、identity |
| Post-closeout | `routes/chat_post_closeout.py` | session memory、observability、distill queue |
| 入口 | `routes/chat_handler.py` | 路由编排 (~253 行) |

## 验证

```bash
pytest tests/test_chat_handler.py tests/test_prompt_memory_recall.py -q
```
