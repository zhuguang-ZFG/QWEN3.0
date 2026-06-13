"""LiMa backend facade: compatibility shim re-exporting registry, constants, and helpers."""
import sys

from backends_constants import (
    CODE_CAPABLE_BACKENDS,
    GFW_BACKENDS,
    IDE_SOURCES,
    KEY_POOL_PREFIXES,
    PUBLIC_MODEL_NAME,
    STRONG_MODELS,
    THINKING_BACKENDS,
    VISION_BACKENDS,
    VISION_SYSTEM_PROMPT,
    WEAK_BACKENDS,
)
from backends_registry import BACKENDS, LM_URL
from backend_utils import (
    backend_has_capability,
    detect_caps,
    detect_protocol,
    detect_tier,
    detect_vendor,
    first_backend_with_capability,
    get_configured,
    infer_key_pool_provider,
    is_enabled,
    is_weak_backend,
    set_enabled,
)


def startup_check() -> None:
    configured = get_configured()
    if configured:
        print(f"[LiMa] {len(configured)} backends configured", file=sys.stderr)
    else:
        print("[LiMa] WARNING: No backends have API keys!", file=sys.stderr)


# Auto-run check on import
startup_check()
