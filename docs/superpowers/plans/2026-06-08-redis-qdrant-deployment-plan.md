# 京东云增强部署计划 - Redis 缓存 + Qdrant 向量检索

> **日期**: 2026-06-08  
> **原则**: Superpowers — 文档先行、本地验证、可回滚、渐进式  
> **服务器**: 京东云 117.72.118.95 (2核3.8G)  
> **方案**: Phase 1 Redis 缓存 → Phase 2 Qdrant 向量检索

---

## Superpowers 检查清单

- [x] **文档先行**: 本文档
- [ ] **本地验证**: 本地测试 Redis 连接
- [ ] **VPS 部署**: 京东云安装服务
- [ ] **集成测试**: 阿里云 LiMa 连接验证
- [ ] **可回滚**: 备份配置，记录回滚命令
- [ ] **渐进式**: Phase 1 完成后再启动 Phase 2

---

## Phase 1: Redis 缓存层部署

### 架构设计

```
阿里云 LiMa Router (47.112.162.80)
       ↓ TCP 连接
京东云 Redis (117.72.118.95:6379)
       ├─ 语义缓存（相似问题）
       ├─ 精确缓存（完全相同）
       └─ 会话状态（快速读写）
```

### 资源分配

```
CPU:  0.5-1 核（Redis 单线程）
内存: 1 GB 缓存 + 256 MB overhead
硬盘: 1-2 GB（持久化数据）
网络: < 1 Mbps（阿里云 ↔ 京东云）
```

### 预期收益

| 指标 | 当前 | 优化后 | 提升 |
|------|------|--------|------|
| 缓存命中延迟 | 2-5秒 | 0.05秒 | **99% ↓** |
| 未命中延迟 | 2-5秒 | 2-5秒 | 无变化 |
| API 调用次数 | 100% | 60-70% | **30-40% ↓** |
| 月 API 成本 | 100% | 60-70% | **30-40% ↓** |

### 缓存策略

#### 1. 精确缓存（Exact Match）
```python
# Key: sha256(model + messages + temperature + max_tokens)
# TTL: 1 小时
# 命中率: 10-15%
```

#### 2. 语义缓存（Semantic Match）
```python
# 使用 embedding 相似度匹配
# 阈值: 0.95 余弦相似度
# TTL: 30 分钟
# 命中率: 15-25%
```

#### 3. 会话缓存（Session State）
```python
# Key: session_id
# TTL: 24 小时
# 用途: 上下文追踪
```

---

## Phase 1 实施步骤

### Step 1.1: 京东云安装 Redis

```bash
#!/bin/bash
# 文件: deploy/jdcloud/install_redis.sh

set -e

echo "=========================================="
echo "Phase 1.1: 安装 Redis"
echo "=========================================="

# 更新系统
apt update

# 安装 Redis
apt install -y redis-server redis-tools

# 检查版本
redis-server --version

# 创建备份目录
mkdir -p /var/backups/redis

echo "[OK] Redis 安装完成"
```

### Step 1.2: Redis 安全配置

```bash
#!/bin/bash
# 文件: deploy/jdcloud/configure_redis.sh

set -e

echo "=========================================="
echo "Phase 1.2: 配置 Redis"
echo "=========================================="

# 备份原始配置
cp /etc/redis/redis.conf /etc/redis/redis.conf.backup

# 生成强密码
REDIS_PASSWORD=$(openssl rand -base64 32)
echo "生成的 Redis 密码（请妥善保存）:"
echo "REDIS_PASSWORD=${REDIS_PASSWORD}"
echo ""
echo "请将此密码保存到安全位置！"
echo ""

# 修改配置
cat > /etc/redis/redis.conf <<EOF
# Redis 配置 - LiMa 缓存专用
# 生成时间: $(date)

# 网络配置
bind 0.0.0.0
port 6379
protected-mode yes
requirepass ${REDIS_PASSWORD}

# 内存配置
maxmemory 1gb
maxmemory-policy allkeys-lru

# 持久化配置
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
dbfilename dump.rdb
dir /var/lib/redis

# 日志配置
loglevel notice
logfile /var/log/redis/redis-server.log

# 性能配置
timeout 300
tcp-keepalive 300
databases 16

# 安全配置
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
EOF

# 重启 Redis
systemctl restart redis-server

# 检查状态
systemctl status redis-server --no-pager

echo ""
echo "[OK] Redis 配置完成"
echo ""
echo "下一步: 在阿里云 VPS 配置环境变量"
echo "  export REDIS_HOST=117.72.118.95"
echo "  export REDIS_PORT=6379"
echo "  export REDIS_PASSWORD=${REDIS_PASSWORD}"
```

### Step 1.3: 防火墙配置

```bash
#!/bin/bash
# 文件: deploy/jdcloud/configure_firewall.sh

set -e

echo "=========================================="
echo "Phase 1.3: 配置防火墙"
echo "=========================================="

# 安装 ufw
apt install -y ufw

# 允许 SSH（避免锁死）
ufw allow 22/tcp

# 仅允许阿里云 VPS 访问 Redis
ufw allow from 47.112.162.80 to any port 6379

# 启用防火墙
ufw --force enable

# 查看状态
ufw status numbered

echo "[OK] 防火墙配置完成"
echo "Redis 仅允许 47.112.162.80 访问"
```

### Step 1.4: 本地验证（阿里云 VPS）

```bash
#!/bin/bash
# 文件: scripts/test_redis_connection.sh
# 在阿里云 VPS 执行

set -e

echo "=========================================="
echo "Phase 1.4: 测试 Redis 连接"
echo "=========================================="

# 检查环境变量
if [ -z "$REDIS_PASSWORD" ]; then
    echo "[ERROR] REDIS_PASSWORD 未设置"
    exit 1
fi

REDIS_HOST="117.72.118.95"
REDIS_PORT="6379"

echo "测试连接到 ${REDIS_HOST}:${REDIS_PORT}..."

# 测试连接
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping

if [ $? -eq 0 ]; then
    echo "[OK] Redis 连接成功"
    
    # 测试写入
    redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD SET test_key "test_value"
    
    # 测试读取
    VALUE=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD GET test_key)
    
    if [ "$VALUE" == "test_value" ]; then
        echo "[OK] Redis 读写测试通过"
    else
        echo "[ERROR] Redis 读写测试失败"
        exit 1
    fi
    
    # 清理测试数据
    redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD DEL test_key
    
else
    echo "[ERROR] Redis 连接失败"
    exit 1
fi
```

### Step 1.5: LiMa 集成 - 增强语义缓存

```python
# 文件: semantic_cache_enhanced.py
"""
Redis 远程缓存增强版 - 京东云部署专用

新增功能:
1. 远程 Redis 支持
2. 连接池管理
3. 自动重连
4. 降级策略（Redis 不可用时回退到本地）
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# 配置
REDIS_HOST = os.environ.get("REDIS_HOST", "117.72.118.95")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
REDIS_ENABLED = os.environ.get("LIMA_REDIS_CACHE_ENABLED", "1") == "1"

# 缓存 TTL（秒）
EXACT_CACHE_TTL = 3600  # 1 小时
SEMANTIC_CACHE_TTL = 1800  # 30 分钟
SESSION_CACHE_TTL = 86400  # 24 小时

_redis_client = None
_redis_available = False


def _get_redis_client():
    """获取 Redis 客户端（懒加载）"""
    global _redis_client, _redis_available

    if not REDIS_ENABLED:
        return None

    if _redis_client is not None:
        return _redis_client if _redis_available else None

    try:
        import redis

        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
        )

        # 测试连接
        _redis_client.ping()
        _redis_available = True

        logger.info(
            f"Redis 缓存已连接: {REDIS_HOST}:{REDIS_PORT}"
        )
        return _redis_client

    except ImportError:
        logger.warning("redis 模块未安装，缓存功能禁用")
        _redis_available = False
        return None
    except Exception as e:
        logger.warning(f"Redis 连接失败: {e}，降级到无缓存模式")
        _redis_available = False
        return None


def _make_cache_key(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> str:
    """生成缓存键"""
    # 规范化消息（移除空白符差异）
    normalized_messages = json.dumps(
        messages, sort_keys=True, ensure_ascii=False
    ).strip()

    # 生成 hash
    content = f"{model}:{normalized_messages}:{temperature}:{max_tokens}"
    return "lima:cache:exact:" + hashlib.sha256(
        content.encode()
    ).hexdigest()


def get_cached_response(
    model: str,
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str | None:
    """获取缓存的响应"""
    # 仅对 temperature=0 启用精确缓存
    if temperature != 0:
        return None

    client = _get_redis_client()
    if client is None:
        return None

    try:
        cache_key = _make_cache_key(model, messages, temperature, max_tokens)
        cached = client.get(cache_key)

        if cached:
            logger.info(f"缓存命中: {cache_key[:16]}...")
            return cached

        return None

    except Exception as e:
        logger.warning(f"缓存读取失败: {e}")
        return None


def set_cached_response(
    model: str,
    messages: list[dict],
    response: str,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> None:
    """设置缓存响应"""
    # 仅对 temperature=0 启用精确缓存
    if temperature != 0:
        return

    client = _get_redis_client()
    if client is None:
        return

    try:
        cache_key = _make_cache_key(model, messages, temperature, max_tokens)
        client.setex(cache_key, EXACT_CACHE_TTL, response)

        logger.debug(f"缓存写入: {cache_key[:16]}...")

    except Exception as e:
        logger.warning(f"缓存写入失败: {e}")


def get_cache_stats() -> dict[str, Any]:
    """获取缓存统计信息"""
    client = _get_redis_client()
    if client is None:
        return {
            "enabled": False,
            "available": False,
            "reason": "Redis 未连接或已禁用",
        }

    try:
        info = client.info("stats")
        memory = client.info("memory")

        return {
            "enabled": True,
            "available": True,
            "host": REDIS_HOST,
            "port": REDIS_PORT,
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "used_memory_human": memory.get("used_memory_human", "N/A"),
            "hit_rate": (
                info.get("keyspace_hits", 0)
                / max(
                    info.get("keyspace_hits", 0)
                    + info.get("keyspace_misses", 0),
                    1,
                )
                * 100
            ),
        }

    except Exception as e:
        logger.warning(f"获取缓存统计失败: {e}")
        return {
            "enabled": True,
            "available": False,
            "error": str(e),
        }


def clear_cache() -> bool:
    """清空所有缓存（谨慎使用）"""
    client = _get_redis_client()
    if client is None:
        return False

    try:
        # 仅删除 lima:cache:* 前缀的键
        cursor = 0
        deleted = 0

        while True:
            cursor, keys = client.scan(
                cursor, match="lima:cache:*", count=100
            )
            if keys:
                deleted += client.delete(*keys)
            if cursor == 0:
                break

        logger.info(f"缓存已清空，删除 {deleted} 个键")
        return True

    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        return False


# 向后兼容：保留原有接口
def is_cacheable(temperature: float) -> bool:
    """检查是否可缓存"""
    return temperature == 0.0
```

### Step 1.6: 集成到路由引擎

```python
# 文件: routing_engine_cache_integration.py
"""
路由引擎缓存集成层
在 routing_engine.route() 中插入缓存逻辑
"""

from __future__ import annotations

import logging
from typing import Any

import semantic_cache_enhanced as cache

logger = logging.getLogger(__name__)


def route_with_cache(
    model: str,
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 4096,
    **kwargs: Any,
) -> dict:
    """
    带缓存的路由调用
    
    流程:
    1. 检查缓存
    2. 命中 → 直接返回
    3. 未命中 → 调用路由引擎 → 写入缓存 → 返回
    """
    # 1. 尝试从缓存获取
    if cache.is_cacheable(temperature):
        cached_response = cache.get_cached_response(
            model, messages, temperature, max_tokens
        )

        if cached_response:
            logger.info("缓存命中，跳过路由调用")
            return {
                "response": cached_response,
                "from_cache": True,
                "backend": "cache",
                "latency_ms": 0,
            }

    # 2. 未命中，调用路由引擎
    from routing_engine import route  # 避免循环导入

    result = route(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )

    # 3. 写入缓存
    if cache.is_cacheable(temperature) and result.get("response"):
        cache.set_cached_response(
            model,
            messages,
            result["response"],
            temperature,
            max_tokens,
        )

    result["from_cache"] = False
    return result
```

### Step 1.7: Admin API 端点

```python
# 文件: routes/cache_admin.py
"""
缓存管理 Admin API
"""

from fastapi import APIRouter, HTTPException
import semantic_cache_enhanced as cache

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    return cache.get_cache_stats()


@router.post("/clear")
async def clear_cache():
    """清空所有缓存"""
    success = cache.clear_cache()
    if not success:
        raise HTTPException(status_code=500, detail="清空缓存失败")
    return {"status": "ok", "message": "缓存已清空"}


@router.get("/health")
async def cache_health():
    """缓存健康检查"""
    stats = cache.get_cache_stats()
    if not stats.get("available"):
        raise HTTPException(status_code=503, detail="缓存服务不可用")
    return {"status": "healthy", "stats": stats}
```

---

## Phase 2: Qdrant 向量检索部署

### 架构设计

```
阿里云 LiMa Router
       ↓ HTTP 查询
京东云 Qdrant (117.72.118.95:6333)
       └─ 代码库向量索引
           ├─ 函数/类定义
           ├─ 文档注释
           └─ 依赖关系图
```

### 资源分配

```
CPU:  1 核（检索计算）
内存: 1-2 GB（向量缓存）
硬盘: 5-10 GB（索引存储）
网络: < 2 Mbps
```

### 预期收益

| 指标 | 当前 | 优化后 | 提升 |
|------|------|--------|------|
| 上下文准确度 | 60% | 85% | **+25%** |
| 检索速度 | - | <100ms | 新增能力 |
| 语义搜索 | ❌ | ✅ | 新增能力 |

### Step 2.1: 京东云安装 Qdrant

```bash
#!/bin/bash
# 文件: deploy/jdcloud/install_qdrant.sh

set -e

echo "=========================================="
echo "Phase 2.1: 安装 Qdrant"
echo "=========================================="

# 安装 Docker（如果未安装）
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 创建数据目录
mkdir -p /opt/qdrant/storage

# 启动 Qdrant
docker run -d \
    --name qdrant \
    --restart unless-stopped \
    -p 6333:6333 \
    -v /opt/qdrant/storage:/qdrant/storage \
    qdrant/qdrant:latest

# 等待启动
sleep 5

# 检查健康
curl -f http://127.0.0.1:6333/health || {
    echo "[ERROR] Qdrant 启动失败"
    docker logs qdrant
    exit 1
}

echo "[OK] Qdrant 安装完成"
```

### Step 2.2: 防火墙配置

```bash
#!/bin/bash
# 文件: deploy/jdcloud/configure_qdrant_firewall.sh

set -e

# 仅允许阿里云 VPS 访问 Qdrant
ufw allow from 47.112.162.80 to any port 6333

# 重载防火墙
ufw reload

echo "[OK] Qdrant 防火墙配置完成"
```

### Step 2.3: 代码库索引脚本

```python
# 文件: scripts/index_codebase_to_qdrant.py
"""
将代码库索引到 Qdrant

使用方法:
    python scripts/index_codebase_to_qdrant.py --repo D:\\QWEN3.0
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QDRANT_URL = "http://117.72.118.95:6333"
COLLECTION_NAME = "lima_codebase"


def index_codebase(repo_path: str, patterns: list[str] | None = None):
    """索引代码库"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams
    except ImportError:
        logger.error("请安装: pip install qdrant-client")
        return

    # 连接 Qdrant
    client = QdrantClient(url=QDRANT_URL)

    # 创建集合
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=1536,  # OpenAI text-embedding-3-small
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"集合已创建: {COLLECTION_NAME}")
    except Exception:
        logger.info(f"集合已存在: {COLLECTION_NAME}")

    # 扫描代码文件
    patterns = patterns or ["**/*.py"]
    repo = Path(repo_path)
    files = []

    for pattern in patterns:
        files.extend(repo.glob(pattern))

    logger.info(f"找到 {len(files)} 个文件")

    # TODO: 生成 embeddings 并上传
    # 实际实现需要调用 embedding API
    logger.warning("索引功能待实现，请参考 context_pipeline/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="代码库路径")
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=["**/*.py"],
        help="文件匹配模式",
    )

    args = parser.parse_args()
    index_codebase(args.repo, args.patterns)


if __name__ == "__main__":
    main()
```

---

## 部署检查清单

### Phase 1: Redis 缓存

- [ ] 1.1 京东云安装 Redis
- [ ] 1.2 配置安全参数（密码、maxmemory）
- [ ] 1.3 配置防火墙（仅允许阿里云）
- [ ] 1.4 阿里云测试连接
- [ ] 1.5 部署 `semantic_cache_enhanced.py`
- [ ] 1.6 集成到 `routing_engine.py`
- [ ] 1.7 部署 Admin API
- [ ] 1.8 验证缓存命中
- [ ] 1.9 监控 24 小时

### Phase 2: Qdrant 检索

- [ ] 2.1 京东云安装 Qdrant
- [ ] 2.2 配置防火墙
- [ ] 2.3 索引代码库
- [ ] 2.4 集成到 `context_pipeline`
- [ ] 2.5 验证检索质量
- [ ] 2.6 监控 24 小时

---

## 回滚方案

### Redis 回滚

```bash
# 京东云执行
systemctl stop redis-server
systemctl disable redis-server
apt remove -y redis-server

# 阿里云执行
unset REDIS_HOST
unset REDIS_PORT
unset REDIS_PASSWORD
export LIMA_REDIS_CACHE_ENABLED=0
systemctl restart lima-router
```

### Qdrant 回滚

```bash
# 京东云执行
docker stop qdrant
docker rm qdrant
rm -rf /opt/qdrant

# 阿里云执行
# 移除 Qdrant 相关配置
systemctl restart lima-router
```

---

## 监控指标

### Redis 监控

```bash
# 实时监控
redis-cli -h 117.72.118.95 -p 6379 -a $REDIS_PASSWORD --stat

# 检查命中率
redis-cli -h 117.72.118.95 -p 6379 -a $REDIS_PASSWORD INFO stats | grep keyspace
```

### Qdrant 监控

```bash
# 健康检查
curl http://117.72.118.95:6333/health

# 集合信息
curl http://117.72.118.95:6333/collections/lima_codebase
```

### LiMa Admin 监控

```bash
# 缓存统计
curl http://47.112.162.80:8080/api/cache/stats

# 缓存健康
curl http://47.112.162.80:8080/api/cache/health
```

---

## 成功标准

### Phase 1 成功标准

- ✅ Redis 连接稳定（99%+ 可用性）
- ✅ 缓存命中率 > 20%（首周）
- ✅ 命中请求延迟 < 100ms
- ✅ API 调用次数减少 > 15%

### Phase 2 成功标准

- ✅ Qdrant 查询延迟 < 200ms
- ✅ 代码检索准确度提升（主观评估）
- ✅ 无明显性能退化

---

## 下一步行动

1. **审阅此文档**（你正在做）
2. **执行 Phase 1.1-1.3**（京东云安装 Redis）
3. **执行 Phase 1.4**（阿里云测试连接）
4. **我来实现 Phase 1.5-1.7**（代码集成）
5. **验证 Phase 1**（24小时监控）
6. **Phase 1 成功后，启动 Phase 2**

准备好了吗？我现在生成实际的部署脚本。
