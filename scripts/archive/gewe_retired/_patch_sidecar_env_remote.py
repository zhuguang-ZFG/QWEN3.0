import secrets
from pathlib import Path

p = Path("/opt/lima-router/.env")
lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
data = {}
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
if not data.get("GEWECHAT_BASE_URL"):
    data["GEWECHAT_BASE_URL"] = "http://127.0.0.1:2531/v2/api"
data["LIMA_CHANNEL_BASE_URL"] = "http://127.0.0.1:8080"
data["GEWECHAT_CALLBACK_URL"] = "http://47.112.162.80:9919/v2/api/callback/collect"
if not data.get("LIMA_WECHAT_SIDECAR_TOKEN"):
    data["LIMA_WECHAT_SIDECAR_TOKEN"] = secrets.token_urlsafe(24)
out = []
seen = set()
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
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("env_ok")
