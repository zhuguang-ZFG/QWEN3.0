"""Merge data/weixin_ilink.env.snippet into /opt/lima-router/.env on VPS."""
from pathlib import Path

REMOTE = Path("/opt/lima-router")
snippet = REMOTE / "data" / "weixin_ilink.env.snippet"
env_path = REMOTE / ".env"

if not snippet.exists():
    print("no_snippet")
    raise SystemExit(0)

data: dict[str, str] = {}
for line in snippet.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()

lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
out, seen = [], set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in data:
            out.append(f"{k}={data[k]}")
            seen.add(k)
        else:
            out.append(line)
    else:
        out.append(line)
for k, v in data.items():
    if k not in seen:
        out.append(f"{k}={v}")
env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
print("weixin_env_merged")
