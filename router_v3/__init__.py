"""
LiMa Router V3 — 三层路由架构
Layer 1: 请求分类器 (classify_request)
Layer 2: 后端池选择 (select_backends)
Layer 3: 执行器 (execute)

设计原则:
- IDE 请求永远不走弱后端
- 后端选择基于实时健康状态
- 同层随机消除死模型
- 全部失败返回诚实错误，不降级到不可接受质量
"""

from backends_constants import IDE_SOURCES

from router_v3.classify import classify_request
from router_v3.ide import detect_ide_by_fingerprints, detect_ide_from_system_prompt
from router_v3.pools import DIRECT_BACKENDS, MAX_FALLBACKS, POOLS
from router_v3.select import select_backends

__all__ = [
    "IDE_SOURCES",
    "POOLS",
    "DIRECT_BACKENDS",
    "MAX_FALLBACKS",
    "classify_request",
    "select_backends",
    "detect_ide_by_fingerprints",
    "detect_ide_from_system_prompt",
]
