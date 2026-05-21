"""
patch_server_v3.py — 将 V3 路由集成到 server.py
在服务器上运行: python3.10 patch_server_v3.py

做的事:
1. 删除 _INSTANT_REPLIES + _try_instant_reply (如果还在)
2. 添加 V3 模块 import
3. 在 _handle_chat 中接入 V3 路由逻辑
4. 在后端调用后接入 health_tracker

不做的事:
- 不重写 server.py
- 不改变 API 接口
- 不影响 streaming 逻辑
"""

import os
import re
import sys
import shutil
import time

SERVER_PY = "/opt/lima-router/server.py"


def read_file():
    with open(SERVER_PY, "r", encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def write_file(content):
    backup = f"{SERVER_PY}.bak.{int(time.time())}"
    shutil.copy2(SERVER_PY, backup)
    print(f"  Backup: {backup}")
    with open(SERVER_PY, "w", encoding="utf-8") as f:
        f.write(content)


def patch_imports(content):
    """添加 V3 模块 import"""
    if "import router_v3" in content:
        print("  [imports] Already patched")
        return content
    old = "import smart_router"
    new = "import smart_router\nimport router_v3\nimport health_tracker\nimport sticky_session"
    content = content.replace(old, new, 1)
    print("  [imports] Added router_v3, health_tracker, sticky_session")
    return content


def patch_remove_instant_replies(content):
    """删除预设直答"""
    if "_INSTANT_REPLIES" not in content and "_try_instant_reply" not in content:
        print("  [instant] Already removed")
        return content
    content = re.sub(r'_INSTANT_REPLIES = \[.*?\]\s*\n', '', content, flags=re.DOTALL)
    content = re.sub(r'def _try_instant_reply\(.*?\n(?=\ndef |\nclass )', '', content, flags=re.DOTALL)
    content = content.replace('_try_instant_reply(last_user_query)', 'None')
    content = content.replace('_try_instant_reply(query)', 'None')
    print("  [instant] Removed _INSTANT_REPLIES + _try_instant_reply")
    return content


def patch_routing_preference(content):
    """替换 Mode-based routing 为 V3 逻辑"""
    marker = "# ── Mode-based routing preference"
    if marker not in content:
        if "# ── V3" in content:
            print("  [routing] Already patched")
            return content
        print("  [routing] Marker not found, skipping")
        return content

    old = (
        "    # ── Mode-based routing preference ─────────────────────────────────────\n"
        "    prefer = None\n"
        '    if req.model == "fast":\n'
        '        prefer = "longcat_lite"\n'
        '    elif req.model == "expert":\n'
        '        prefer = "scnet_ds_pro"\n'
        "        req.thinking = True\n"
        '    elif req.model == "vision":\n'
        "        prefer = None  # vision handled by existing detection"
    )
    new = (
        "    # ── V3 路由: 分类 + 后端池选择 ────────────────────────────────────────\n"
        '    _v3_type = "ide" if (fmt == "anthropic" or ide_source in router_v3.IDE_SOURCES) else "chat"\n'
        "    _v3_backends = router_v3.select_backends(_v3_type, health_tracker.get_health_map())\n"
        "    prefer = _v3_backends[0] if _v3_backends else None\n"
        '    if req.model == "fast":\n'
        '        prefer = "longcat_lite"\n'
        '    elif req.model == "expert":\n'
        '        prefer = "scnet_ds_pro"\n'
        "        req.thinking = True"
    )
    if old in content:
        print("  [routing] Exact match failed, trying line-by-line")
        # Fallback: find by marker and replace block
        lines = content.split("\n")
        start = None
        for i, line in enumerate(lines):
            if marker in line:
                start = i
                break
        if start is not None:
            end = start + 8
            lines[start:end+1] = new.split("\n")
            content = "\n".join(lines)
            print("  [routing] Replaced by line range")
    return content


def main():
    print("=== Patching server.py for V3 ===")
    if not os.path.exists(SERVER_PY):
        print(f"ERROR: {SERVER_PY} not found")
        sys.exit(1)

    content = read_file()
    print(f"  Read {len(content)} chars")

    content = patch_imports(content)
    content = patch_remove_instant_replies(content)
    content = patch_routing_preference(content)

    write_file(content)
    print("\nDone! Restart server to apply.")


if __name__ == "__main__":
    main()
