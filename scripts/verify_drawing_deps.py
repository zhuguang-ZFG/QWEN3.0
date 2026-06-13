#!/usr/bin/env python3
"""验证绘画引擎依赖是否正确安装"""

import importlib.util
import sys


def _check(module_name: str, attr: str = "__version__") -> tuple[bool, str]:
    """Return (ok, info) for a module without importing it."""
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False, "not found"
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, attr, "imported")
        return True, str(version)
    except ImportError as exc:
        return False, str(exc)


def verify_dependencies() -> bool:
    """验证所有绘画引擎依赖"""
    errors = []

    checks = [
        ("svgpathtools", "__version__"),
        ("shapely", "__version__"),
        ("dashscope", "__version__"),
        ("PIL", "__version__"),
        ("alembic", "__version__"),
    ]

    for module_name, attr in checks:
        ok, info = _check(module_name, attr)
        if ok:
            print(f"[OK] {module_name} {info}")
        else:
            errors.append(f"[FAIL] {module_name}: {info}")

    # 位图矢量化（可选，检查多个可能的包）
    potrace_available = False
    for module_name in ("pypotrace", "potracer"):
        ok, info = _check(module_name)
        if ok:
            print(f"[OK] {module_name} {info}")
            potrace_available = True

    if not potrace_available:
        print("[WARN] potrace: not found (pypotrace or potracer)")
        print("       Suggestion: pip install potracer")

    if errors:
        print("\nError summary:")
        for err in errors:
            print(f"  {err}")
        return False

    print("\n[SUCCESS] All core dependencies verified!")
    return True


if __name__ == "__main__":
    success = verify_dependencies()
    sys.exit(0 if success else 1)
