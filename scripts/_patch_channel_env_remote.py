"""One-shot VPS env patch for channel gateway (uploaded by deploy_channel_gateway.py)."""
import secrets
from pathlib import Path

env_path = Path("/opt/lima-router/.env")
lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
data = {}
for line in lines:
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    data[k.strip()] = v.strip().strip('"').strip("'")

flags = {
    "WECHAT_BRIDGE_ENABLED": "1",
    "LIMA_CHANNEL_TOOLS": "1",
    "LIMA_CHANNEL_SESSION": "1",
    "LIMA_CHANNEL_AUTO_GUEST_BIND": "1",
    "LIMA_CHANNEL_DB_PATH": "data/channel_gateway.db",
    "LIMA_CHANNEL_VOICE_REPLY": "1",
    "LIMA_CHANNEL_INVITE_QR": "1",
}
data.update(flags)

if not data.get("LIMA_CHANNEL_ID_SALT"):
    data["LIMA_CHANNEL_ID_SALT"] = secrets.token_hex(16)
if not data.get("LIMA_WECHAT_SIDECAR_TOKEN"):
    data["LIMA_WECHAT_SIDECAR_TOKEN"] = secrets.token_urlsafe(24)

out = []
seen = set()
for line in lines:
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    k = line.split("=", 1)[0].strip()
    if k in data:
        out.append(f"{k}={data[k]}")
        seen.add(k)
    else:
        out.append(line)
for k, v in data.items():
    if k not in seen:
        out.append(f"{k}={v}")
env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
print("env_patch_ok salt_set=yes token_set=yes")
