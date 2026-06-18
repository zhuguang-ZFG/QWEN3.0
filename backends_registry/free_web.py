"""免费网页 AI 后端定义（lza6 系列、Pollinations、SCNet 等）"""

from backends_registry.free_web_ddg import BACKENDS as _ddg
from backends_registry.free_web_pollinations import BACKENDS as _pollinations
from backends_registry.free_web_workers import BACKENDS as _workers

BACKENDS: dict[str, dict] = {}
BACKENDS.update(_ddg)
BACKENDS.update(_workers)
BACKENDS.update(_pollinations)
