"""Remove GeWe sidecar nginx snippet from chat.donglicao.com.conf on VPS."""
from pathlib import Path

CONF = Path("/etc/nginx/conf.d/chat.donglicao.com.conf")
MARK = "# LiMa WeChat sidecar (GeWeAPI webhook"

text = CONF.read_text(encoding="utf-8")
if MARK not in text:
    print("nginx_already_clean")
    raise SystemExit(0)

lines = text.splitlines(keepends=True)
out: list[str] = []
i = 0
while i < len(lines):
    if MARK in lines[i]:
        while i < len(lines) and "location ^~ /telegram/" not in lines[i]:
            i += 1
        continue
    out.append(lines[i])
    i += 1

CONF.write_text("".join(out), encoding="utf-8")
print("nginx_unpatched")
