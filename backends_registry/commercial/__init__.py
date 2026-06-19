"""Commercial backend registry, split by provider family."""

from .cerebras_family import BACKENDS as _cerebras_family
from .chinese import BACKENDS as _chinese
from .platforms import BACKENDS as _platforms
from .opengateway import BACKENDS as _opengateway

BACKENDS: dict[str, dict] = {}
BACKENDS.update(_cerebras_family)
BACKENDS.update(_chinese)
BACKENDS.update(_platforms)
BACKENDS.update(_opengateway)

__all__ = ["BACKENDS"]
