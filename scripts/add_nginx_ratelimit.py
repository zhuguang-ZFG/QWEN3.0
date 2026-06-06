"""Add nginx rate limiting to LiMa server."""

NGINX_CONF = "/etc/nginx/nginx.conf"
SITE_CONF = "/etc/nginx/conf.d/chat.donglicao.com.conf"

# 1. Add limit_req_zone to nginx.conf http block
with open(NGINX_CONF) as f:
    content = f.read()

if "limit_req_zone" not in content:
    zones = (
        "\n    # LiMa rate limiting\n"
        "    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;\n"
        "    limit_req_zone $binary_remote_addr zone=agent:10m rate=5r/s;\n"
        "    limit_req_zone $binary_remote_addr zone=webhook:10m rate=10r/s;\n"
    )
    content = content.replace("http {", "http {" + zones, 1)
    with open(NGINX_CONF, "w") as f:
        f.write(content)
    print("Added limit_req_zone to nginx.conf")
else:
    print("limit_req_zone already exists")

# 2. Add rate limits to site config
with open(SITE_CONF) as f:
    content = f.read()

changed = False

if "limit_req zone=agent" not in content:
    content = content.replace(
        "location ^~ /agent/ {",
        "location ^~ /agent/ {\n        limit_req zone=agent burst=10 nodelay;",
        1,
    )
    changed = True

if "limit_req zone=webhook" not in content:
    content = content.replace(
        "location ^~ /telegram/ {",
        "location ^~ /telegram/ {\n        limit_req zone=webhook burst=20 nodelay;",
        1,
    )
    changed = True

if changed:
    with open(SITE_CONF, "w") as f:
        f.write(content)
    print("Added rate limits to site config")
else:
    print("Rate limits already in site config")
