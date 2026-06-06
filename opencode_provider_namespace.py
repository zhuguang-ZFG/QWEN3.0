"""opencode_provider_namespace.py — ProviderOptions 命名空间键映射。

复刻 OpenCode provider/transform.ts 的 providerOptions() (L1200-1248)。

AI SDK 按命名空间键读取 providerOptions。如果键名错误，
所有选项 (store/reasoningEffort/thinkingConfig 等) 被静默忽略。

核心映射规则:
  - Azure: { openai: opts, azure: opts } (双键)
  - Gateway: { gateway: cachingOpts, <slug>: providerOpts }
  - OpenAI-compatible: providerID.split(".")[0]
  - 标准: { [sdkKey]: options }

源码参考:
  - opencode-source/packages/opencode/src/provider/transform.ts (L1200-1248)
"""

from __future__ import annotations

import logging
import re
from typing import Any

_log = logging.getLogger(__name__)

# ── Provider kind → SDK namespace key 映射 ──────────────────────────────────
# 大部分 provider 的 namespace key 就是 provider kind 本身
_PK_TO_NAMESPACE: dict[str, str | list[str]] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google",
    "azure": ["openai", "azure"],          # 双键 (transform.ts:1210-1215)
    "bedrock": "bedrock",
    "openrouter": "openrouter",
    "github_copilot": "github-copilot",
    "groq": "groq",
    "xai": "xai",
    "mistral": "mistral",
    "cerebras": "cerebras",
    "deepinfra": "deepinfra",
    "fireworks": "fireworks-ai",
    "together": "togetherai",
    "perplexity": "perplexity",
    "sambanova": "sambanova",
    "nvidia": "nvidia",
    "opencode_zen": "opencode",
    "venice": "venice",
    "deepseek": "deepseek",
    "kimi": "moonshot",
    "openai_compatible": "openai-compatible",  # split(".")[0] 等效
}

# ── Gateway slug 映射 (transform.ts:1226-1240) ─────────────────────────────
# Gateway 从 URL 路径中提取上游 provider slug
_GATEWAY_SLUG_MAP: dict[str, str] = {
    "openai": "openai",
    "amazon": "bedrock",
    "bedrock": "bedrock",
    "anthropic": "anthropic",
    "google": "google",
    "mistral": "mistral",
    "meta": "meta",
    "cohere": "cohere",
}

# Gateway 缓存选项键
_GATEWAY_CACHE_KEY = "gateway"


def resolve_provider_namespace_key(
    pk: str,
    backend_name: str = "",
    model_id: str = "",
) -> list[str]:
    """解析 providerOptions 的命名空间键。

    复刻 transform.ts providerOptions() (L1200-1248)。

    Args:
        pk: Provider kind (detect_provider_kind 的返回值)。
        backend_name: 后端名称 (用于 Gateway slug 提取)。
        model_id: 模型标识符。

    Returns:
        命名空间键列表 (可能包含多个键，如 Azure 的 ["openai", "azure"])。
    """
    # Azure: 双键
    if pk == "azure":
        return ["openai", "azure"]

    # Gateway: gateway + slug
    if pk == "ai_gateway" or pk == "gateway":
        keys = [_GATEWAY_CACHE_KEY]
        slug = _extract_gateway_slug(backend_name)
        if slug:
            keys.append(slug)
        return keys

    # OpenAI-compatible: split(".")[0] 逻辑
    if pk == "openai_compatible":
        # 从 backend_name 提取第一段作为 key
        key = _extract_compatible_key(backend_name)
        return [key] if key else ["openai-compatible"]

    # 标准映射
    ns = _PK_TO_NAMESPACE.get(pk)
    if ns:
        if isinstance(ns, list):
            return ns
        return [ns]

    # 回退: 使用 pk 本身
    return [pk]


def wrap_provider_options(
    options: dict[str, Any],
    namespace_keys: list[str],
) -> dict[str, Any]:
    """将选项包装到正确的 providerOptions 命名空间键下。

    Args:
        options: 原始选项 dict (如 {"store": false, "reasoningEffort": "high"})。
        namespace_keys: 命名空间键列表。

    Returns:
        包装后的 providerOptions dict。

    示例:
        wrap_provider_options(
            {"store": False},
            ["openai", "azure"]
        )
        → {"openai": {"store": False}, "azure": {"store": False}}
    """
    if not options or not namespace_keys:
        return {}

    result: dict[str, Any] = {}
    for key in namespace_keys:
        # 每个 key 都获得完整的选项副本
        result[key] = dict(options)

    return result


def build_provider_options_for_body(
    session_options: dict[str, Any],
    pk: str,
    backend_name: str = "",
    model_id: str = "",
) -> dict[str, Any]:
    """构建可直接放入请求体的 providerOptions。

    组合 resolve_provider_namespace_key() + wrap_provider_options()。

    Args:
        session_options: resolve_session_options() 返回的选项。
        pk: Provider kind。
        backend_name: 后端名称。
        model_id: 模型标识符。

    Returns:
        可直接合并到请求 body 的 providerOptions dict。
    """
    if not session_options:
        return {}

    keys = resolve_provider_namespace_key(pk, backend_name, model_id)
    return wrap_provider_options(session_options, keys)


def _extract_gateway_slug(backend_name: str) -> str:
    """从 Gateway 后端名称中提取上游 provider slug。

    例如:
        "gw_openai_gpt4" → "openai"
        "gateway_amazon_bedrock" → "bedrock"

    Args:
        backend_name: 后端名称。

    Returns:
        Gateway slug 或空字符串。
    """
    bn = backend_name.lower()
    # Remove common gateway prefixes
    for prefix in ("gw_", "gateway_"):
        if bn.startswith(prefix):
            bn = bn[len(prefix):]
            break

    # Match against known slugs
    for slug_key, slug_val in _GATEWAY_SLUG_MAP.items():
        if slug_key in bn:
            return slug_val

    return ""


def _extract_compatible_key(backend_name: str) -> str:
    """从 OpenAI-compatible 后端名称中提取 namespace key。

    复刻 providerID.split(".")[0] 逻辑。

    Args:
        backend_name: 后端名称 (如 "scnet_ds_flash", "cfai_qwen_coder")。

    Returns:
        提取的 key 或空字符串。
    """
    bn = backend_name.lower()

    # 尝试从常见前缀推断
    prefix_map = {
        "scnet": "deepseek",        # SCNet 主要跑 DeepSeek
        "scnet_large": "deepseek",
        "cfai": "cloudflare",       # Cloudflare AI
        "cf": "cloudflare",
        "nvidia": "nvidia",
        "sambanova": "sambanova",
        "deepinfra": "deepinfra",
        "fireworks": "fireworks-ai",
    }

    for prefix, key in prefix_map.items():
        if bn.startswith(prefix):
            return key

    # 回退: 使用第一个 "-" 前的部分
    parts = bn.split("_", 1)
    return parts[0] if parts else bn
