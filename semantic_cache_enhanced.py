# -*- coding: utf-8 -*-
"""
Redis 远程缓存增强版 - 京东云部署专用

新增功能:
1. 远程 Redis 支持（京东云 117.72.118.95）
2. 连接池管理
3. 自动重连和降级
4. 缓存统计和监控

环境变量:
    REDIS_HOST=117.72.118.95
    REDIS_PORT=6379
    REDIS_PASSWORD=<京东云生成的密码>
    LIMA_REDIS_CACHE_ENABLED=1
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

# Key 前缀
CACHE_PREFIX = "lima:cache:"

_redis_client = None
_redis_available = False
_connection_attempts = 0
_max_connection_attempts = 3


def _get_redis_client():
    """获取 Redis 客户端（懒加载 + 自动重连）"""
    global _redis_client, _redis_available, _connection_attempts

    if not REDIS_ENABLED:
        return None

    # 已连接且可用
    if _redis_client is not None and _redis_available:
        return _redis_client

    # 超过最大重连次数
    if _connection_attempts >= _max_connection_attempts:
        return None

    try:
        import redis

        _connection_attempts += 1

        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
            retry_on_timeout=True,
            max_connections=50,
        )

        # 测试连接
        _redis_client.ping()
        _redis_available = True
        _connection_attempts = 0  # 重置计数

        logger.info(
            f"Redis 缓存已连接: {REDIS_HOST}:{REDIS_PORT}"
        )
        return _redis_client

    except ImportError:
        logger.warning("redis 模块未安装，缓存功能禁用")
        logger.warning("安装: pip install redis")
        _redis_available = False
        return None
    except Exception as e:
        logger.warning(
            f"Redis 连接失败 (尝试 {_connection_attempts}/{_max_connection_attempts}): {e}"
        )
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
    hash_key = hashlib.sha256(content.encode()).hexdigest()

    return f"{CACHE_PREFIX}exact:{hash_key}"


def get_cached_response(
    model: str,
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str | None:
    """
    获取缓存的响应

    Args:
        model: 模型名称
        messages: 消息列表
        temperature: 温度参数（仅 temperature=0 启用缓存）
        max_tokens: 最大 token 数

    Returns:
        缓存的响应文本，未命中返回 None
    """
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
            logger.info(f"缓存命中: {cache_key[:32]}...")
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
    """
    设置缓存响应

    Args:
        model: 模型名称
        messages: 消息列表
        response: 响应文本
        temperature: 温度参数
        max_tokens: 最大 token 数
    """
    # 仅对 temperature=0 启用精确缓存
    if temperature != 0:
        return

    # 空响应不缓存
    if not response or not response.strip():
        return

    client = _get_redis_client()
    if client is None:
        return

    try:
        cache_key = _make_cache_key(model, messages, temperature, max_tokens)
        client.setex(cache_key, EXACT_CACHE_TTL, response)

        logger.debug(f"缓存写入: {cache_key[:32]}... (TTL={EXACT_CACHE_TTL}s)")

    except Exception as e:
        logger.warning(f"缓存写入失败: {e}")


def get_cache_stats() -> dict[str, Any]:
    """
    获取缓存统计信息

    Returns:
        统计信息字典，包含命中率、内存使用等
    """
    client = _get_redis_client()
    if client is None:
        return {
            "enabled": REDIS_ENABLED,
            "available": False,
            "reason": "Redis 未连接或已禁用",
            "host": REDIS_HOST,
            "port": REDIS_PORT,
        }

    try:
        info = client.info("stats")
        memory = client.info("memory")

        keyspace_hits = info.get("keyspace_hits", 0)
        keyspace_misses = info.get("keyspace_misses", 0)
        total_requests = keyspace_hits + keyspace_misses

        return {
            "enabled": True,
            "available": True,
            "host": REDIS_HOST,
            "port": REDIS_PORT,
            "keyspace_hits": keyspace_hits,
            "keyspace_misses": keyspace_misses,
            "total_requests": total_requests,
            "hit_rate": (
                (keyspace_hits / total_requests * 100)
                if total_requests > 0
                else 0.0
            ),
            "used_memory": memory.get("used_memory", 0),
            "used_memory_human": memory.get("used_memory_human", "N/A"),
            "connected_clients": client.info("clients").get("connected_clients", 0),
        }

    except Exception as e:
        logger.warning(f"获取缓存统计失败: {e}")
        return {
            "enabled": True,
            "available": False,
            "error": str(e),
        }


def clear_cache() -> bool:
    """
    清空所有 LiMa 缓存

    Returns:
        成功返回 True，失败返回 False
    """
    client = _get_redis_client()
    if client is None:
        return False

    try:
        # 仅删除 lima:cache:* 前缀的键
        cursor = 0
        deleted = 0

        while True:
            cursor, keys = client.scan(
                cursor, match=f"{CACHE_PREFIX}*", count=100
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


def is_cacheable(temperature: float) -> bool:
    """
    检查请求是否可缓存

    Args:
        temperature: 温度参数

    Returns:
        temperature=0 时返回 True
    """
    return temperature == 0.0


# ============================================================
# 向后兼容接口（兼容旧的 semantic_cache.py）
# ============================================================

def get(model: str, messages: list[dict], temperature: float = 0.0) -> str | None:
    """
    旧接口兼容：获取缓存

    Args:
        model: 模型名称
        messages: 消息列表
        temperature: 温度参数

    Returns:
        缓存的响应，未命中返回 None
    """
    return get_cached_response(model, messages, temperature)


def set(model: str, messages: list[dict], response: str, temperature: float = 0.0) -> None:
    """
    旧接口兼容：设置缓存

    Args:
        model: 模型名称
        messages: 消息列表
        response: 响应文本
        temperature: 温度参数
    """
    set_cached_response(model, messages, response, temperature)


# ============================================================
# 连接和统计
# ============================================================

def get_connection_status() -> dict[str, Any]:
    """
    获取连接状态

    Returns:
        连接状态信息
    """
    return {
        "enabled": REDIS_ENABLED,
        "available": _redis_available,
        "connection_attempts": _connection_attempts,
        "max_attempts": _max_connection_attempts,
        "host": REDIS_HOST,
        "port": REDIS_PORT,
    }


# 向后兼容：保留原有函数签名
def get_semantic_cache(query: str, threshold: float = 0.95) -> str | None:
    """
    语义缓存（预留接口，暂未实现）

    Args:
        query: 查询文本
        threshold: 相似度阈值

    Returns:
        缓存的响应，未命中返回 None
    """
    # TODO: 实现基于 embedding 的语义缓存
    return None


def set_semantic_cache(query: str, response: str) -> None:
    """
    设置语义缓存（预留接口，暂未实现）

    Args:
        query: 查询文本
        response: 响应文本
    """
    # TODO: 实现基于 embedding 的语义缓存
    pass
