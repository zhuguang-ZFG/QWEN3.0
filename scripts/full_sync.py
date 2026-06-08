#!/usr/bin/env python3
"""全量同步本地代码到 VPS"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VPS_HOST = "root@47.112.162.80"
VPS_PATH = "/opt/lima-router/"
SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519")

# 排除的文件和目录
EXCLUDE_PATTERNS = [
    ".git/",
    ".venv*/",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    "node_modules/",
    ".env",
    ".env.local",
    "*.log",
    "*.db",
    "*.db-journal",
    ".ruff_cache/",
    ".mypy_cache/",
    "test_*.html",
    "test_*.py",
]

def main():
    """使用 rsync 全量同步"""

    # 构建排除参数
    exclude_args = []
    for pattern in EXCLUDE_PATTERNS:
        exclude_args.extend(["--exclude", pattern])

    # rsync 命令
    cmd = [
        "rsync",
        "-avz",  # archive, verbose, compress
        "--delete",  # 删除目标端多余的文件
        "-e", f"ssh -i {SSH_KEY}",
        *exclude_args,
        str(REPO_ROOT) + "/",  # 源目录（注意末尾的 /）
        f"{VPS_HOST}:{VPS_PATH}",  # 目标
    ]

    print(f"同步 {REPO_ROOT} -> {VPS_HOST}:{VPS_PATH}")
    print("排除的模式:", ", ".join(EXCLUDE_PATTERNS[:5]), "...")
    print()

    # 执行同步
    result = subprocess.run(cmd, cwd=REPO_ROOT)

    if result.returncode == 0:
        print("\n✓ 同步完成")
        print("\n重启服务...")
        restart_cmd = [
            "ssh", "-i", SSH_KEY, VPS_HOST,
            "systemctl restart lima-router"
        ]
        subprocess.run(restart_cmd)
        print("✓ 服务已重启")
    else:
        print("\n✗ 同步失败")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
