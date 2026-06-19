"""Coding-pool backend registry, split by provider family."""

from .modelscope import BACKENDS as _modelscope
from .third_party import BACKENDS as _third_party
from .community import BACKENDS as _community

BACKENDS: dict[str, dict] = {}
BACKENDS.update(_modelscope)
BACKENDS.update(_third_party)
BACKENDS.update(_community)

__all__ = ["BACKENDS"]
