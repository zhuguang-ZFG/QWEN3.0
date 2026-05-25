"""Patch VPS .env for GeWeAPI cloud + public HTTPS callback."""
import os
import secrets
from pathlib import Path

p = Path("/opt/lima-router/.env")
lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
data: dict[str, str] = {}
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()

data["GEWECHAT_BASE_URL"] = "https://www.geweapi.com/gewe/v2/api"
data["GEWECHAT_CALLBACK_URL"] = os.environ.get(
    "GEWECHAT_CALLBACK_URL",
    "https://chat.donglicao.com/gewe/v2/api/callback/collect",
)
data["LIMA_CHANNEL_BASE_URL"] = "http://127.0.0.1:8080"
token = os.environ.get("GEWECHAT_TOKEN", "").strip()
if token:
    data["GEWECHAT_TOKEN"] = token
app_id = os.environ.get("GEWECHAT_APP_ID", "").strip()
if app_id:
    data["GEWECHAT_APP_ID"] = app_id
if not data.get("LIMA_WECHAT_SIDECAR_TOKEN"):
    data["LIMA_WECHAT_SIDECAR_TOKEN"] = secrets.token_urlsafe(24)

out: list[str] = []
seen: set[str] = set()
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
print("env_ok", "token=" + ("set" if data.get("GEWECHAT_TOKEN") else "missing"))
