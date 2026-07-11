#!/usr/bin/env node
/**
 * One-shot: send code review task to AtomCode via local A2A MCP bridge (streamable-http).
 * Usage: node scripts/a2a_atomcode_review.js
 *
 * Streamable-http protocol:
 *   Initialize: POST to MCP_URL, get mcp-session-id from response header
 *   All subsequent requests: POST with mcp-session-id header + Accept: application/json, text/event-stream
 *   Response body is SSE format (event: message / data: {...})
 */

const MCP_URL = process.env.A2A_MCP_URL || "http://127.0.0.1:41242/mcp";
const ATOMCODE_URL = "http://127.0.0.1:4940";
const TIMEOUT_MS = Number(process.env.A2A_REVIEW_TIMEOUT_MS || 300000);

const REVIEW_PROMPT = `请对以下项目进行只读 code review（不要修改任何文件）。

项目路径: D:\\QWEN3.0
项目: DLC 绘图服务 — Python 3.10 + FastAPI → ESP32 设备网关

当前生产链路:
server_dlc.py → dlc_api/ → dlc_core/ → device_gateway/ → ESP32
小程序 → /device/v1/app/*

近期重点（请优先审查）:
1. 语音栈: device_voice/, routes/device_app_voice.py, routes/device_app_voice_ws.py
2. 架构边界与退役路径（旧 routing_engine 已删除）
3. 安全: 无硬编码密钥、ticket TTL、WS 鉴权
4. 测试覆盖: tests/test_device_app_voice.py 等
5. 生产配置: LIMA_VOICE_* / dashscope ASR

审查输出格式:
## 总体评价
## 优点
## 问题（按 P0/P1/P2 分级，含文件路径）
## 建议改进
## 测试/部署风险

请基于实际代码阅读给出具体、可操作的反馈，避免泛泛而谈。`;

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
        clientInfo: { name: "dlc-atomcode-review", version: "1.0.0" },
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

  console.error(`[a2a] Listing agents...`);
  const agentsRaw = await client.call("tools/call", { name: "list_agents", arguments: {} });
  console.error(`[a2a] Agents: ${extractText(agentsRaw).slice(0, 500)}`);

  console.error(`[a2a] Sending review to AtomCode (${ATOMCODE_URL}), timeout ${TIMEOUT_MS}ms...`);
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
