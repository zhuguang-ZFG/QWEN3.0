#!/usr/bin/env node
/**
 * One-shot: dispatch an implementation brief to MiMo via local A2A MCP bridge.
 * Usage:
 *   node scripts/a2a_mimo_dispatch.js .tmp/brief_mimo_split_device_app_tasks.md
 *   node scripts/a2a_mimo_dispatch.js --message "inline prompt"
 *
 * Env:
 *   A2A_MCP_URL (default http://127.0.0.1:41242/mcp)
 *   A2A_MIMO_URL (default http://127.0.0.1:4939)
 *   A2A_REVIEW_TIMEOUT_MS (default 900000)
 */
const fs = require("fs");
const path = require("path");

const MCP_URL = process.env.A2A_MCP_URL || "http://127.0.0.1:41242/mcp";
const MIMO_URL = process.env.A2A_MIMO_URL || "http://127.0.0.1:4939";
const TIMEOUT_MS = Number(process.env.A2A_REVIEW_TIMEOUT_MS || 900000);

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

class HttpMcpClient {
  constructor(mcpUrl) {
    this.mcpUrl = mcpUrl;
    this.sessionId = null;
    this.nextId = 1;
  }

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
    const initId = this.nextId++;
    const initBody = {
      jsonrpc: "2.0",
      id: initId,
      method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "a2a-mimo-dispatch", version: "1.0.0" },
      },
    };
    const res = await fetch(this.mcpUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
      },
      body: JSON.stringify(initBody),
    });
    if (!res.ok) throw new Error(`initialize failed: ${res.status} ${res.statusText}`);
    this.sessionId = res.headers.get("mcp-session-id");
    if (!this.sessionId) throw new Error("missing mcp-session-id header");
    await this._readSseMessages(res);
    await this.notify("notifications/initialized", {});
  }

  async call(method, params, timeoutMs) {
    const id = this.nextId++;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(this.mcpUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json, text/event-stream",
          "mcp-session-id": this.sessionId,
        },
        body: JSON.stringify({ jsonrpc: "2.0", id, method, params }),
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
          } catch (_) {
            continue;
          }
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
        Accept: "application/json, text/event-stream",
        "mcp-session-id": this.sessionId,
      },
      body: JSON.stringify({ jsonrpc: "2.0", method, params }),
    });
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

function loadPrompt(argv) {
  if (argv.includes("--message")) {
    const i = argv.indexOf("--message");
    return argv.slice(i + 1).join(" ").trim();
  }
  const fileArg = argv.find((a) => !a.startsWith("-"));
  if (!fileArg) {
    throw new Error("Usage: node scripts/a2a_mimo_dispatch.js <brief.md> | --message <text>");
  }
  const full = path.resolve(fileArg);
  if (!fs.existsSync(full)) throw new Error(`brief not found: ${full}`);
  return fs.readFileSync(full, "utf8");
}

async function main() {
  const prompt = loadPrompt(process.argv.slice(2));
  console.error(`[a2a] Connecting MCP: ${MCP_URL}`);
  const client = new HttpMcpClient(MCP_URL);
  await client.connect();
  console.error(`[a2a] Session ID: ${client.sessionId}`);
  console.error(`[a2a] Dispatch to MiMo (${MIMO_URL}), timeout ${TIMEOUT_MS}ms, prompt ${prompt.length} chars`);

  const result = await client.call(
    "tools/call",
    {
      name: "send_message",
      arguments: {
        agent_url: MIMO_URL,
        message: prompt,
      },
    },
    TIMEOUT_MS
  );

  if (result?.isError) {
    throw new Error(`MiMo call returned isError: ${extractText(result)}`);
  }
  const text = extractText(result);
  console.log(text || JSON.stringify(result, null, 2));
}

main().catch((err) => {
  console.error(`[a2a] ERROR: ${err.message}`);
  process.exit(1);
});
