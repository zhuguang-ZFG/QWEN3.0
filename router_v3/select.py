"""Backend selection for LiMa Router V3."""

import logging

import runtime_topology

from config.node_role import is_free_backend_only
from router_v3.pools import DIRECT_BACKENDS, MAX_FALLBACKS, POOLS

logger = logging.getLogger(__name__)

# 云上好获取、无需本地代理或付费 key 的后端，用于 free_backend_only 节点。
_CLOUD_FREE_BACKENDS: set[str] = {
    "pollinations",
    "pollinations_openai",
    "ddg_gpt4o_mini",
    "ddg_gpt5_mini",
    "ddg_claude_haiku_45",
    "ddg_tinfoil_gptoss_120b",
    "ovh_llama70b",
    "ovh_deepseek",
    "google_flash",
    "google_flash_lite",
    "google_pro",
    "chat_ubi",
    "deepseek_free",
    "jdcloud_pollinations_openai",
    "jdcloud_pollinations_deepseek",
}


def _free_backend_only_allowed(names: list[str]) -> list[str]:
    """Filter backends to the cloud-free subset on auxiliary nodes."""
    return [name for name in names if name in _CLOUD_FREE_BACKENDS]


def select_backends(req_type: str, health_map: dict, proxy_healthy: bool = True) -> list:
    """从对应 Pool 选健康后端，同层随机，P2C 优化"""
    pool = POOLS.get(req_type, POOLS["chat"])
    overlay_tiers = _overlay_tiers_for_pool(req_type)
    result = []

    for tier in ("strong", "medium", "floor"):
        candidates = list(pool.get(tier, []))
        candidates.extend(overlay_tiers.get(tier, []))
        if not proxy_healthy:
            candidates = [b for b in candidates if b in DIRECT_BACKENDS]
        usable = [b for b in candidates if health_map.get(b, "healthy") != "dead"]
        usable = runtime_topology.filter_backends(usable)
        if is_free_backend_only():
            usable = _free_backend_only_allowed(usable)
        # Keep declared order as priority (no shuffle)
        result.extend(usable)

    if not result:
        result = [b for b in DIRECT_BACKENDS if health_map.get(b, "healthy") != "dead"]
        result = runtime_topology.filter_backends(result)
        if is_free_backend_only():
            result = _free_backend_only_allowed(result)

    # 极端保底：只加非 dead 的
    if not result:
        result = [b for b in ["chat_ubi", "pollinations"] if health_map.get(b, "healthy") != "dead"]

    return result[:MAX_FALLBACKS]


def _overlay_tiers_for_pool(pool_key: str) -> dict[str, list[str]]:
    try:
        from backend_admission_store import get_overlay_backends_by_tier
    except ImportError as exc:
        logger.warning("backend_admission_store not installed; overlay tiers disabled: %s", exc)
        return {"medium": [], "floor": []}
    grouped = get_overlay_backends_by_tier(pool_key)
    return {
        "strong": grouped.get("strong", []),
        "medium": grouped.get("medium", []) + grouped.get("late_fallback", []),
        "floor": grouped.get("floor", []),
    }


def get_cloud_free_backends() -> set[str]:
    """Return the set of backends allowed on free_backend_only nodes."""
    return set(_CLOUD_FREE_BACKENDS)
