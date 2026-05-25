"""Insert WeChat sidecar nginx snippet into chat.donglicao.com.conf on VPS."""
from pathlib import Path

CONF = Path("/etc/nginx/conf.d/chat.donglicao.com.conf")
SNIPPET = Path("/opt/lima-router/chat.donglicao.com.wechat-sidecar.snippet.conf")
MARK = "# LiMa WeChat sidecar (GeWeAPI webhook"

text = CONF.read_text(encoding="utf-8")
if MARK in text:
    print("nginx_already")
    raise SystemExit(0)
snippet = SNIPPET.read_text(encoding="utf-8")
needle = "    location ^~ /telegram/"
if needle not in text:
    print("nginx_anchor_missing")
    raise SystemExit(1)
text = text.replace(needle, snippet + "\n" + needle, 1)
CONF.write_text(text, encoding="utf-8")
print("nginx_patched")
