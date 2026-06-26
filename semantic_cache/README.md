# 语义缓存层（P4-5）

`semantic_cache/` 提供基于 embedding 相似度的 LLM 响应缓存，用于降低高频问题的后端调用成本。

## 设计

- `Embedder` 协议支持可插拔 embedder。
  - `JinaEmbedder`：使用 `code_context.embedding_client` 调用 Jina AI（需配置 `JINA_API_KEY`）。
  - `FakeEmbedder`：离线确定性向量，用于测试和无 Jina key 环境。
- `SemanticCacheStore`：SQLite 持久化，按 `query_hash` 唯一索引，支持 TTL 裁剪与命中计数。
- `SemanticCache`：高阶 API，负责 embedding、相似度计算、命中返回、未命中写入。

## 配置

通过环境变量开关（默认关闭）：

```bash
# 启用语义缓存
LIMA_SEMANTIC_CACHE_ENABLED=1
# 相似度阈值（默认 0.92）
LIMA_SEMANTIC_CACHE_THRESHOLD=0.92
# TTL 秒数（默认 3600）
LIMA_SEMANTIC_CACHE_TTL=3600
# SQLite 路径（默认 data/semantic_cache.db）
LIMA_SEMANTIC_CACHE_DB=data/semantic_cache.db
# Embedding 维度（默认 256，需与 JinaEmbedder 一致）
LIMA_SEMANTIC_CACHE_DIMENSIONS=256
```

## 使用

```python
from semantic_cache import SemanticCache

cache = SemanticCache()
response = cache.lookup("今天北京天气怎么样")
if response is None:
    response = call_llm(...)
    cache.store_response("今天北京天气怎么样", response)
```

## 注意

当前为基座实现，尚未接入生产请求路径。后续集成时请保持默认关闭，先在灰度环境验证命中率与响应质量。
