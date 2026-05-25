"""Print .env key names and whether values are non-empty (no secret values)."""
from pathlib import Path

p = Path("/opt/lima-router/.env")
if not p.exists():
    print("no_env")
    raise SystemExit(1)
for line in p.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        k = k.strip()
        if k.startswith(("GEWECHAT_", "LIMA_WECHAT", "WECHAT_")):
            print(k, "set" if v.strip() else "empty")
