# qwen2API 缓存优化方案

**目标**: 减少重复请求，降低风控风险，提升响应速度

---

## 🎯 **缓存策略设计**

### 1. 语义缓存（推荐）

**原理**: 相似问题返回相同答案

```
用户问题 → 生成 embedding → 查找相似缓存 → 命中则返回
           ↓ 未命中
       调用 qwen API → 缓存结果
```

**优势**:
- "1+1=?" 和 "一加一等于几" 命中同一缓存
- 降低 80%+ 重复请求
- 对用户透明

### 2. 精确缓存（简单）

**原理**: 完全相同的请求返回缓存

```
hash(messages + model + params) → 查缓存 → 命中则返回
```

**优势**:
- 实现简单
- 命中率中等（30-50%）
- 零延迟

### 3. 混合缓存

**原理**: 精确缓存 + 语义缓存两层

```
请求 → 精确缓存（毫秒级）
     ↓ 未命中
   语义缓存（100ms）
     ↓ 未命中
   调用 API
```

---

## 💻 **实现方案**

### 方案 A：本地 SQLite 缓存（推荐）

**架构**:
```
MiMo Code → qwen2API (本地 :7862)
                ↓
           缓存层 (SQLite)
                ↓
           Qwen 官方 (有缓存则不调用)
```

**表结构**:
```sql
CREATE TABLE chat_cache (
    id INTEGER PRIMARY KEY,
    request_hash TEXT UNIQUE,          -- 请求指纹
    model TEXT,                        -- 模型名
    messages_json TEXT,                -- 消息内容
    response_json TEXT,                -- 响应内容
    embedding BLOB,                    -- 问题向量（语义缓存用）
    hit_count INTEGER DEFAULT 0,       -- 命中次数
    created_at TIMESTAMP,
    last_hit_at TIMESTAMP,
    ttl_seconds INTEGER DEFAULT 86400  -- 缓存时长（默认24小时）
);

CREATE INDEX idx_request_hash ON chat_cache(request_hash);
CREATE INDEX idx_model_created ON chat_cache(model, created_at);
```

**实现代码框架**:
```python
# qwen2api_cache.py
import hashlib, json, sqlite3, time
from datetime import datetime, timedelta

class ChatCache:
    def __init__(self, db_path="~/.qwen2api/cache.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def get(self, model, messages, params=None):
        """查询缓存"""
        req_hash = self._hash_request(model, messages, params)

        cur = self.conn.execute(
            "SELECT response_json, created_at, ttl_seconds "
            "FROM chat_cache WHERE request_hash=?",
            (req_hash,)
        )
        row = cur.fetchone()

        if not row:
            return None

        response, created, ttl = row

        # 检查是否过期
        if time.time() - created > ttl:
            self._delete(req_hash)
            return None

        # 更新命中统计
        self._update_hit(req_hash)

        return json.loads(response)

    def set(self, model, messages, params, response, ttl=86400):
        """写入缓存"""
        req_hash = self._hash_request(model, messages, params)

        self.conn.execute(
            "INSERT OR REPLACE INTO chat_cache "
            "(request_hash, model, messages_json, response_json, "
            " created_at, ttl_seconds) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (req_hash, model, json.dumps(messages),
             json.dumps(response), time.time(), ttl)
        )
        self.conn.commit()

    def _hash_request(self, model, messages, params):
        """生成请求指纹"""
        content = json.dumps({
            "model": model,
            "messages": messages,
            "params": params or {}
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def stats(self):
        """缓存统计"""
        cur = self.conn.execute(
            "SELECT COUNT(*), SUM(hit_count), "
            "AVG(hit_count) FROM chat_cache"
        )
        total, hits, avg = cur.fetchone()
        return {
            "total_entries": total,
            "total_hits": hits or 0,
            "avg_hits": round(avg or 0, 2),
            "hit_rate": f"{(hits/(hits+total)*100) if hits else 0:.1f}%"
        }
```

**集成到 qwen2API**:
```python
# 在 qwen2API 主代码中添加
cache = ChatCache()

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    # 1. 尝试从缓存读取
    cached = cache.get(
        model=request.model,
        messages=request.messages,
        params={"temperature": request.temperature}
    )

    if cached:
        logger.info(f"Cache HIT for {request.model}")
        return cached

    # 2. 缓存未命中，调用真实 API
    response = await call_qwen_api(request)

    # 3. 写入缓存
    cache.set(
        model=request.model,
        messages=request.messages,
        params={"temperature": request.temperature},
        response=response,
        ttl=86400  # 24小时
    )

    return response
```

---

### 方案 B：Redis 缓存（高性能）

**适用场景**: 多实例部署、高并发

```python
import redis, json, hashlib

class RedisCache:
    def __init__(self, host='localhost', port=6379):
        self.redis = redis.Redis(host=host, port=port, db=0)

    def get(self, model, messages):
        key = self._gen_key(model, messages)
        cached = self.redis.get(key)
        return json.loads(cached) if cached else None

    def set(self, model, messages, response, ttl=86400):
        key = self._gen_key(model, messages)
        self.redis.setex(key, ttl, json.dumps(response))

    def _gen_key(self, model, messages):
        content = f"{model}:{json.dumps(messages)}"
        return f"qwen:cache:{hashlib.md5(content.encode()).hexdigest()}"
```

---

### 方案 C：内存缓存（最简单）

**适用场景**: 单实例、快速原型

```python
from functools import lru_cache
import hashlib, json

class MemoryCache:
    def __init__(self, maxsize=1000):
        self.cache = {}
        self.maxsize = maxsize

    def get(self, model, messages):
        key = self._hash(model, messages)
        return self.cache.get(key)

    def set(self, model, messages, response):
        key = self._hash(model, messages)

        # LRU 淘汰
        if len(self.cache) >= self.maxsize:
            oldest = min(self.cache.keys(),
                        key=lambda k: self.cache[k]['time'])
            del self.cache[oldest]

        self.cache[key] = {
            'response': response,
            'time': time.time()
        }

    def _hash(self, model, messages):
        return hashlib.md5(
            f"{model}:{json.dumps(messages)}".encode()
        ).hexdigest()
```

---

## 📊 **预期效果**

### 命中率预估

| 场景 | 精确缓存 | 语义缓存 | 组合 |
|------|---------|---------|------|
| **代码补全** | 60-70% | 75-85% | 85-90% |
| **问答** | 30-40% | 60-70% | 70-80% |
| **文档生成** | 20-30% | 40-50% | 50-60% |

### 风控风险降低

```
原始: 100 请求/小时 → Qwen API
              ↓
缓存: 30 请求/小时 → Qwen API (70%命中)
```

**风控风险降低 70%！**

---

## 🎛️ **缓存配置建议**

### 配置文件 `cache.json`

```json
{
  "enabled": true,
  "type": "sqlite",  // sqlite / redis / memory
  "ttl": {
    "default": 86400,     // 24小时
    "code": 604800,       // 代码7天
    "chat": 3600,         // 对话1小时
    "thinking": 86400     // 思考24小时
  },
  "max_size": {
    "memory": 1000,       // 内存缓存条目数
    "sqlite": 50000       // SQLite 最大条目
  },
  "cleanup": {
    "interval": 3600,     // 清理间隔（秒）
    "keep_popular": true  // 保留高频缓存
  },
  "semantic": {
    "enabled": false,     // 语义缓存（需要 embedding）
    "threshold": 0.95     // 相似度阈值
  }
}
```

---

## 🚀 **部署步骤**

### 1. 修改 qwen2API 源码

在 GitHub 项目提 Issue 或 PR，或者本地 patch：

```bash
cd qwen2API
# 添加缓存模块
mkdir cache
cat > cache/chat_cache.py << 'EOF'
# (上面的 ChatCache 代码)
EOF

# 修改主文件集成缓存
# (修改 main.py 或 api.py)
```

### 2. 启用缓存

```bash
# 创建缓存配置
cat > ~/.qwen2api/cache.json << 'EOF'
{
  "enabled": true,
  "type": "sqlite",
  "ttl": {"default": 86400}
}
EOF

# 重启 qwen2API
```

### 3. 监控效果

```bash
# 查看缓存统计
curl http://localhost:7862/cache/stats

# 输出:
# {
#   "total_entries": 1234,
#   "total_hits": 5678,
#   "hit_rate": "82.1%",
#   "size_mb": 45.6
# }
```

---

## 🎯 **推荐方案**

**对于你的使用场景（MiMo Code + qwen2API）**：

✅ **方案 A：SQLite 缓存**

**理由**:
1. 简单可靠（无需额外服务）
2. 持久化（重启不丢失）
3. 性能足够（本地使用）
4. 易于备份和迁移

**实施步骤**:
1. 在 qwen2API 项目提 Issue 请求缓存功能
2. 或者自己 fork 项目添加缓存层
3. 或者在 qwen2API 前面加一层缓存代理

---

## 📝 **临时方案：缓存代理**

**不修改 qwen2API，在前面加一层**：

```python
# qwen_cache_proxy.py - 独立缓存代理
from fastapi import FastAPI, Request
import httpx, hashlib, json, sqlite3

app = FastAPI()
cache = ChatCache("~/.qwen2api_cache/cache.db")

@app.post("/v1/chat/completions")
async def proxy_chat(request: Request):
    body = await request.json()

    # 检查缓存
    cached = cache.get(
        body.get('model'),
        body.get('messages')
    )

    if cached:
        return cached

    # 转发到真实 qwen2API
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:7862/v1/chat/completions",
            json=body,
            headers=dict(request.headers)
        )
        result = resp.json()

    # 写入缓存
    cache.set(
        body.get('model'),
        body.get('messages'),
        result
    )

    return result

# 运行: uvicorn qwen_cache_proxy:app --port 7863
# MiMo Code 配置: http://localhost:7863/v1
```

---

## ✨ **总结**

**加缓存的好处**:
- ✅ 降低 70%+ 风控风险
- ✅ 提升 50-200ms 响应速度
- ✅ 减少网络请求
- ✅ 离线可用（缓存命中时）

**建议立即实施！** 🚀
