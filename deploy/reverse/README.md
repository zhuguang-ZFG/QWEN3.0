# Reverse Sidecar Deploy Templates

These templates are for disabled-by-default reverse provider sidecars. They must bind only to `127.0.0.1` and must not be added to production routing until adapter health and eval evidence exist.

## SCNet Large Web Chat

SCNet large uses the public Web Chat backend discovered at `https://www.scnet.cn/ui/chatbot/`. The effective API prefix is `/acx`; the confirmed send endpoint is `https://www.scnet.cn/acx/chatbot/v1/chat/completion`.

```bash
cp /opt/lima-router/deploy/reverse/scnet-large.service /etc/systemd/system/lima-scnet-reverse.service
systemctl daemon-reload
systemctl enable --now lima-scnet-reverse.service
curl -sf http://127.0.0.1:4505/health
```

The sidecar remains unavailable until all are present:

- `SCNET_REVERSE_ENABLED=1`
- `/opt/lima-router/reverse_gateway_state/scnet_protocol.json`
- `/opt/lima-router/reverse_gateway_state/scnet_cookies.json`

Optional long-context file bridge:

- `SCNET_REVERSE_ENABLE_FILE_CONTEXT=1` uploads prompts above the threshold as a private SCNet text attachment.
- `SCNET_REVERSE_FILE_CONTEXT_THRESHOLD_CHARS=10000` controls when the bridge is used.
- `SCNET_REVERSE_FILE_CONTEXT_CHUNK_CHARS=45000` keeps each text attachment under the Web Chat file parser limit.
- `SCNET_REVERSE_FILE_CONTEXT_MAX_FILES=30` caps chunk count for future parser changes.
- `SCNET_REVERSE_FILE_CONTEXT_MAX_TOTAL_CHARS=50000` fails fast above the current SCNet Web Chat total file parser limit.
- `SCNET_REVERSE_TIMEOUT_SECONDS=180` is recommended for 1M-context file upload plus response latency.

## Private SCNet Cookie State

Browser cookie exports must be provisioned only into the VPS private state directory:

```bash
mkdir -p /opt/lima-router/reverse_gateway_state
chmod 700 /opt/lima-router/reverse_gateway_state
python /opt/lima-router/scripts/provision_scnet_cookies.py \
  /root/scnet_cookies.json \
  /opt/lima-router/reverse_gateway_state/scnet_cookies.json
chmod 600 /opt/lima-router/reverse_gateway_state/scnet_cookies.json
systemctl restart lima-scnet-reverse.service
```

Do not commit cookie exports or copied state files. Reverse gateway health only exposes redacted cookie values.

## Protocol Template

Store this file only on the VPS private state path, then refine `payload_template` after a real browser/XHR capture if SCNet changes required fields:

```json
{
  "endpoint": "https://www.scnet.cn/acx/chatbot/v1/chat/completion",
  "method": "POST",
  "headers": {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.scnet.cn",
    "Referer": "https://www.scnet.cn/ui/chatbot/"
  },
  "payload_template": {
    "conversationId": "",
    "content": "",
    "thinkingEnable": false,
    "onlineEnable": true,
    "modelId": 520,
    "textFile": [],
    "imageFile": [],
    "autoRun": 0,
    "clusterId": "",
    "history": [],
    "tools": [],
    "mcpServers": []
  },
  "stream": true
}
```

The adapter maps OpenAI-compatible input into `content`, optional `history`, `modelId`, `tools`, and `mcpServers`. Browser/XHR capture confirmed the real send endpoint is `/acx/chatbot/v1/chat/completion`, which returns SSE-style `data:{...}` chunks. Direct text input rejects around the Web Chat text limit, so the sidecar can bridge medium prompts through SCNet OSS text attachments when `SCNET_REVERSE_ENABLE_FILE_CONTEXT=1`. Browser capture verified `textFile` attachments are read by the model, but current SCNet Web Chat still rejects raw 1M total attachment text; use retrieval/MCP chunk selection for 1M-scale coding context. Extra tool/MCP fields are accepted by the endpoint; actual remote tool execution still requires SCNet-side MCP configuration.

## Kimi Web Chat (port 4504)

Kimi uses the moonshot.cn Web Chat backend. The local proxy (`D:/ollama_server/kimi_proxy.js`) wraps Kimi's internal API as an OpenAI-compatible endpoint.

### VPS Cookie Deployment

```bash
mkdir -p /opt/lima-router/reverse_gateway_state
chmod 700 /opt/lima-router/reverse_gateway_state

# Upload cookie export from local machine
scp kimi.txt root@<vps>:/root/kimi_cookies.json

# Provision into private state
python /opt/lima-router/scripts/provision_kimi_cookies.py \
  /root/kimi_cookies.json \
  /opt/lima-router/reverse_gateway_state/kimi_cookies.json

chmod 600 /opt/lima-router/reverse_gateway_state/kimi_cookies.json
systemctl restart kimi-proxy
```

### Kimi Cookie Health Check

```bash
# Quick smoke test
curl -s -X POST http://127.0.0.1:4504/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"kimi","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'

# Via keepalive (installed by default)
python /opt/lima-router/scripts/reverse_proxy_keepalive.py
```

### Cookie Refresh

- **Kimi `kimi-auth` JWT**: 有效期约 1 年（access token, membership level 10）
- Token 到期前一个月：从浏览器重新登录 `kimi.com`，导出 Cookie → 重新运行 `provision_kimi_cookies.py`
- 目前无自动 Playwright 刷新（Kimi 登录需要手机号+验证码，VPS 上不可行）

## SCNet + Kimi Health Monitoring

`reverse_proxy_keepalive.py` (cron: `*/30 * * * *`) 监控全部 4 个逆向后端：

| 代理 | 端口 | 测试模型 | 自动刷新 | 告警方式 |
|------|------|---------|---------|---------|
| longcat-web | 4506 | longcat-web | ✅ Playwright | ntfy + log |
| mimo | 4507 | mimo-web-flash | ❌ | ntfy + log |
| kimi | 4504 | kimi | ❌ | ntfy + log |
| scnet-large | 4505 | deepseek-v4-flash | ❌ | ntfy + log |

```bash
# Install cron
cp /opt/lima-router/scripts/reverse_proxy_keepalive.py /opt/lima-router/
(crontab -l 2>/dev/null; echo "*/30 * * * * python3.10 /opt/lima-router/reverse_proxy_keepalive.py") | crontab -

# Manual run
python3.10 /opt/lima-router/reverse_proxy_keepalive.py
```
