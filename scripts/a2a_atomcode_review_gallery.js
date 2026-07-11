#!/usr/bin/env node
/**
 * Gallery feature review via local A2A MCP bridge (streamable-http) -> AtomCode.
 * Usage: node scripts/a2a_atomcode_review_gallery.js
 *
 * Streamable-http protocol:
 *   Initialize: POST to MCP_URL, get mcp-session-id from response header
 *   All subsequent requests: POST with mcp-session-id header + Accept: application/json, text/event-stream
 *   Response body is SSE format (event: message / data: {...})
 */

const MCP_URL = process.env.A2A_MCP_URL || "http://127.0.0.1:41242/mcp";
const ATOMCODE_URL = "http://127.0.0.1:4940";
const TIMEOUT_MS = Number(process.env.A2A_REVIEW_TIMEOUT_MS || 600000);

const REVIEW_PROMPT = `请对以下图库功能做独立、只读 code review（不要修改文件，不要读取 .env 密钥）。

项目: D:\\QWEN3.0 (DLC FastAPI) + 子模块 esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile

近期已合并提交（请基于实际代码阅读）:
- fdb81fae feat(gallery): thumb_token auth, gallery_image_id draw, thumb proxy
- bed878d2 fix(ci): migration order, auth payload, voiceprint test mocks
- e26072ee feat(gallery): HMAC token purpose scoping; deps pillow/uvicorn/cryptography/hypothesis
- 6c51909d chore(deps): fastapi 0.139, opencv 5, scikit-image 0.25, dashscope 1.26
- 544aa19b chore(site-v2): npm bumps (next/react-dom/sharp)

审查范围:

【后端】
- routes/device_app_gallery.py — thumb_token/fetch_token 鉴权、代理、删图清缓存
- device_gateway/gallery_service.py — HMAC purpose 分域、stable URL、代理缓存、限流
- device_gateway/task_draw_params.py — gallery_image_id 内部解析 URL，不落库 token
- device_gateway/gallery_store.py — 元数据、软删
- device_gateway/image_url_validation.py — SSRF 白名单
- tests/test_device_app_gallery_*.py, tests/test_gallery_hmac_tokens.py, tests/test_task_creation_gallery_image_id.py

【小程序】（子模块 manager-mobile，若可读）
- src/api/gallery/, src/utils/galleryPreload.ts
- gallery-panel.vue, useDeviceActions.ts — draw_generated + gallery_image_id

重点审查:
1. 安全: thumb vs file token 互斥、JWT access_token 查询参数泄露、删图后 token 重放、跨账号隔离
2. 正确性: gallery_image_id 绘图链路、删图 404、多 worker 代理缓存一致性
3. 性能: thumb 是否拉全图、列表签发 token 频率、内存缓存上限
4. 依赖升级风险: opencv 5 / fastapi 0.139 对绘图链路影响
5. 测试盲区

输出格式:
## 总体评价
## 优点
## 问题（P0/P1/P2，含文件路径、描述、建议）
## 测试盲区
## 部署/回归风险`;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

class HttpMcpClient {
  constructor(mcpUrl) {
    this.mcpUrl = mcpUrl;
    this.sessionId = null;
    this.nextId = 1;
  }

  /** Parse SSE response body and return parsed JSON-RPC messages. */
  async _readSseMessages(res) {
    const text = await res.text();
    const messages = [];
    const lines = text.split("\n");
    let current = {};
    for (const raw of lines) {
      const line = raw.trimEnd();
      if (line === "") {
        if (current.event || current.data) {
          messages.push(current);
          current = {};
        }
        continue;
      }
      if (line.startsWith("event: ")) current.event = line.slice(7);
      else if (line.startsWith("data: ")) current.data = (current.data || "") + line.slice(6) + "\n";
    }
    if (current.event || current.data) messages.push(current);
    return messages;
  }

  async connect() {
    // Step 1: initialize → get sessionId from response header
    const initId = this.nextId++;
    const initBody = {
      jsonrpc: "2.0",
      id: initId,
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: { name: "dlc-atomcode-gallery-review", version: "1.0.0" },
      },
    };
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    let res;
    try {
      res = await fetch(this.mcpUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json, text/event-stream" },
        body: JSON.stringify(initBody),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
    if (!res.ok) throw new Error(`Initialize failed: ${res.status} ${res.statusText}`);
    this.sessionId = res.headers.get("mcp-session-id");
    if (!this.sessionId) throw new Error("No mcp-session-id header in initialize response");

    // Parse SSE body for initialize result
    const events = await this._readSseMessages(res);
    for (const ev of events) {
      if (ev.event === "message" && ev.data) {
        let msg;
        try {
          msg = JSON.parse(ev.data);
        } catch (_) { continue; }
        if (String(msg.id) === String(initId) && msg.error) {
          throw new Error(msg.error.message || JSON.stringify(msg.error));
        }
        // initialize result received
      }
    }

    // Step 2: notifications/initialized (no id, 202 empty body)
    const noteRes = await fetch(this.mcpUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": this.sessionId,
      },
      body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
    });
    if (!noteRes.ok && noteRes.status !== 202) {
      throw new Error(`notifications/initialized failed: ${noteRes.status} ${noteRes.statusText}`);
    }
  }

  async call(method, params, timeoutMs = 60000) {
    const id = this.nextId++;
    const body = { jsonrpc: "2.0", id, method, params };
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(this.mcpUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json, text/event-stream",
          "mcp-session-id": this.sessionId,
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok && res.status !== 202) {
        throw new Error(`POST ${method} failed: ${res.status} ${res.statusText}`);
      }
      const events = await this._readSseMessages(res);
      for (const ev of events) {
        if (ev.event === "message" && ev.data) {
          let msg;
          try {
            msg = JSON.parse(ev.data);
          } catch (_) { continue; }
          if (String(msg.id) === String(id)) {
            if (msg.error) throw new Error(msg.error.message || JSON.stringify(msg.error));
            return msg.result;
          }
        }
      }
      throw new Error(`No response for ${method} (id=${id})`);
    } finally {
      clearTimeout(timer);
    }
  }

  notify(method, params) {
    return fetch(this.mcpUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": this.sessionId,
      },
      body: JSON.stringify({ jsonrpc: "2.0", method, params }),
    });
  }

  close() {
    // streamable-http has no persistent connection to close
  }
}

function extractText(result) {
  if (!result) return "";
  if (typeof result === "string") return result;
  if (result.message) return String(result.message);
  const content = result.content;
  if (typeof content === "string") {
    try {
      const parsed = JSON.parse(content);
      return parsed.message || parsed.text || content;
    } catch {
      return content;
    }
  }
  if (Array.isArray(content)) {
    return content.map((c) => c.text || c.content || JSON.stringify(c)).join("\n");
  }
  return JSON.stringify(result, null, 2);
}

async function main() {
  console.error(`[a2a] Connecting MCP: ${MCP_URL}`);
  const client = new HttpMcpClient(MCP_URL);
  await client.connect();
  console.error(`[a2a] Session ID: ${client.sessionId}`);

  console.error(`[a2a] Sending gallery review to AtomCode (${ATOMCODE_URL}), timeout ${TIMEOUT_MS}ms...`);
  const reviewResult = await client.call(
    "tools/call",
    {
      name: "send_message",
      arguments: {
        agent_url: ATOMCODE_URL,
        message: REVIEW_PROMPT,
      },
    },
    TIMEOUT_MS
  );

  if (reviewResult?.isError) {
    throw new Error(`Review call returned isError: ${extractText(reviewResult)}`);
  }

  const text = extractText(reviewResult);
  console.log(text || JSON.stringify(reviewResult, null, 2));
}

main().catch((err) => {
  console.error(`[a2a] ERROR: ${err.message}`);
  process.exit(1);
});