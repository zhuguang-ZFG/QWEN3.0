#!/usr/bin/env node
/**
 * Ask AtomCode (A2A :4940) to review the NewAPI Kimi fast-path improvement plan.
 * Usage: node scripts/a2a_atomcode_review_newapi_plan.js
 *
 * Streamable-http protocol:
 *   Initialize: POST to MCP_URL, get mcp-session-id from response header
 *   All subsequent requests: POST with mcp-session-id header + Accept: application/json, text/event-stream
 *   Response body is SSE format (event: message / data: {...})
 */

const fs = require("fs");
const path = require("path");

const MCP_URL = process.env.A2A_MCP_URL || "http://127.0.0.1:41242/mcp";
const ATOMCODE_URL = process.env.A2A_ATOMCODE_URL || "http://127.0.0.1:4940";
const TIMEOUT_MS = Number(process.env.A2A_REVIEW_TIMEOUT_MS || 600000);
const PLAN_PATH =
  process.env.A2A_PLAN_PATH ||
  path.join(__dirname, "..", "docs", "ops", "NEWAPI_KIMI_IMPROVEMENT_PLAN_CN.md");
const FAST_TUNE_PATH = path.join(__dirname, "..", "deploy", "jdcloud", "apply_newapi_fast_tune.sh");

function buildPrompt() {
  const plan = fs.readFileSync(PLAN_PATH, "utf8");
  const tune = fs.existsSync(FAST_TUNE_PATH)
    ? fs.readFileSync(FAST_TUNE_PATH, "utf8")
    : "(missing apply_newapi_fast_tune.sh)";
  return `你是资深 LLM 网关 / NewAPI / Kimi Code CLI 运维审查员。请对以下「快路径改善方案」做独立、只读审核（不要修改任何文件，不要索要或打印密钥）。

## 背景（已核实的现网）
- 公网: https://api.donglicao.com → 阿里云反代 → 京东云 117.72.118.95:3000
- 目录: /opt/newapi
- 数据: SQLite ./data/one-api.db（容器未配 SQL_DSN）
- Redis: compose 内 redis:7-alpine，REDIS_CONN_STRING=redis://redis:6379，MEMORY_CACHE_ENABLED=true
- 已有: STREAMING_TIMEOUT=300, FORCE_STREAM_OPTION=true
- 缺失: CRYPTO_SECRET, SESSION_SECRET；SSE 建议 600
- 客户端主路径: Kimi Code CLI；LiteLLM 已退役
- 改密码必须改 SQLite，改 MySQL 无效（曾踩坑）

## 待审方案全文
路径: ${PLAN_PATH}

\`\`\`markdown
${plan}
\`\`\`

## 配套快路径脚本
路径: ${FAST_TUNE_PATH}

\`\`\`bash
${tune}
\`\`\`

## 请重点审查
1. 快路径 Step A–D 是否真能「15 分钟见效」？有无遗漏必做项？
2. CRYPTO_SECRET / SESSION_SECRET / STREAMING_TIMEOUT 对 NewAPI 缓存与 SSE 的实际作用是否说对？
3. 把 MySQL 迁移后置是否合理？有无隐藏风险？
4. Claude anthropic-beta Header 与 Kimi CLI 固定模型是否足够？LinuxDo 上 cch/attribution 问题是否应在快路径提及？
5. apply_newapi_fast_tune.sh 脚本正确性与回滚安全性
6. 验收指标是否可操作

## 输出格式（中文）
## 总体评价
## 方案优点
## 问题（P0/P1/P2：描述 + 建议改法）
## 对快路径的修订建议（可直接粘贴进文档的短段落）
## 是否建议立刻执行 Step A
`;
}

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
        clientInfo: { name: "dlc-atomcode-newapi-plan-review", version: "1.0.0" },
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
  const prompt = buildPrompt();
  console.error(`[a2a] plan=${PLAN_PATH} bytes=${prompt.length}`);
  console.error(`[a2a] Connecting MCP: ${MCP_URL}`);
  const client = new HttpMcpClient(MCP_URL);
  await client.connect();
  console.error(`[a2a] Session ID: ${client.sessionId}`);

  const agentsRaw = await client.call("tools/call", { name: "list_agents", arguments: {} });
  console.error(`[a2a] Agents: ${extractText(agentsRaw).slice(0, 800)}`);

  console.error(`[a2a] Sending plan review to AtomCode (${ATOMCODE_URL}), timeout ${TIMEOUT_MS}ms...`);
  const reviewResult = await client.call(
    "tools/call",
    {
      name: "send_message",
      arguments: {
        agent_url: ATOMCODE_URL,
        message: prompt,
      },
    },
    TIMEOUT_MS
  );

  const text = extractText(reviewResult);
  console.log(text || JSON.stringify(reviewResult, null, 2));
}

main().catch((err) => {
  console.error(`[a2a] ERROR: ${err.message}`);
  process.exit(1);
});