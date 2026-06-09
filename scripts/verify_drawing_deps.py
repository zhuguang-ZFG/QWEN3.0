#!/usr/bin/env python3
"""验证绘画引擎依赖是否正确安装"""

import sys

def verify_dependencies():
    """验证所有绘画引擎依赖"""
    errors = []

    # 1. SVG 路径解析
    try:
        import svgpathtools
        print(f"[OK] svgpathtools imported")
    except ImportError as e:
        errors.append(f"[FAIL] svgpathtools: {e}")

    # 2. 几何计算
    try:
        import shapely
        print(f"[OK] shapely {shapely.__version__}")
    except ImportError as e:
        errors.append(f"[FAIL] shapely: {e}")

    # 3. DashScope SDK
    try:
        import dashscope
        version = getattr(dashscope, '__version__', 'imported')
        print(f"[OK] dashscope {version}")
    except ImportError as e:
        errors.append(f"[FAIL] dashscope: {e}")

    # 4. Pillow
    try:
        from PIL import Image
        import PIL
        print(f"[OK] Pillow {PIL.__version__}")
    except ImportError as e:
        errors.append(f"[FAIL] Pillow: {e}")

    # 5. Alembic
    try:
        import alembic
        print(f"[OK] alembic {alembic.__version__}")
    except ImportError as e:
        errors.append(f"[FAIL] alembic: {e}")

    # 6. 位图矢量化（可选，检查多个可能的包）
    potrace_available = False
    try:
        import pypotrace
        print(f"[OK] pypotrace found")
        potrace_available = True
    except ImportError:
        pass

    try:
        import potracer
        print(f"[OK] potracer {potracer.__version__}")
        potrace_available = True
    except ImportError:
        pass

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
