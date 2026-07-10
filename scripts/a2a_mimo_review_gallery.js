#!/usr/bin/env node
/**
 * Gallery preload feature review via local A2A MCP bridge -> MiMo.
 * Usage: node scripts/a2a_mimo_review_gallery.js
 */

const SSE_URL = process.env.A2A_SSE_URL || "http://127.0.0.1:41242/sse";
const MIMO_URL = "http://127.0.0.1:4939";
const TIMEOUT_MS = Number(process.env.A2A_REVIEW_TIMEOUT_MS || 600000);

const REVIEW_PROMPT = `请对以下图库功能做独立、只读 code review（不要修改文件，不要读取 .env 密钥）。

项目: D:\\QWEN3.0 (DLC FastAPI) + 子模块 esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile

审查范围（含已提交 + 工作区未提交改动）:

【后端 — 已提交 1281d676 + 未提交 total 分页】
- routes/device_app_gallery.py — /thumb /file /download 代理、fetch_token 鉴权、列表 total
- device_gateway/gallery_service.py — stable URL、HMAC fetch_token、代理缓存、限流
- device_gateway/gallery_storage.py — Telegram 存储抽象
- device_gateway/gallery_store.py — count_images、update_thumb_url
- tests/test_device_app_gallery_*.py, tests/test_gallery_storage.py

【小程序 — 已提交 9f81a93 + 未提交 v2 优化】
- src/api/gallery/gallery.ts — 分页 GALLERY_PAGE_SIZE=24、上传 onProgressUpdate
- src/utils/galleryPreload.ts — 分批 preload、去重 Set
- src/pages/v2/device-detail/composables/useGalleryList.ts — 分页/滚动加载
- src/pages/v2/device-detail/components/gallery-panel.vue — 进度条、预览、删除确认
- src/utils/formatBytes.ts
- useDeviceActions.ts — draw_generated + image_url（非 draw_from_image）

重点审查:
1. 安全: access_token/fetch_token 在 URL、JWT 泄露面、draw_generated image_url SSRF、fetch_token 重放
2. 性能: thumb 代理是否下载全图、预加载重复、分页 COUNT 查询、内存缓存
3. 正确性: total/count 契约、分页 hasMore、prependImage totalCount、服务端 draw 拉取 /file
4. 测试盲区与前后端部署顺序（total 字段）
5. 小程序 UX: 预览用 thumb 非全图、滚动加载竞态

输出格式:
## 总体评价
## 优点
## 问题（P0/P1/P2，含文件路径、描述、建议）
## 测试盲区
## 与常见审查偏差的自我校验`;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

class SseMcpClient {
  constructor(sseUrl) {
    this.sseUrl = sseUrl;
    this.messageUrl = null;
    this.pending = new Map();
    this.nextId = 1;
  }

  async connect() {
    const res = await fetch(this.sseUrl);
    if (!res.ok) throw new Error(`SSE GET failed: ${res.status} ${res.statusText}`);
    this.reader = res.body.getReader();
    this.decoder = new TextDecoder();
    this.buffer = "";
    this.messageUrl = await this._waitForEndpoint();
    this._startReading();
  }

  async _waitForEndpoint() {
    while (!this.messageUrl) {
      const { done, value } = await this.reader.read();
      if (done) throw new Error("SSE closed before endpoint event");
      this._append(value);
    }
    return this.messageUrl;
  }

  _append(chunk) {
    this.buffer += this.decoder.decode(chunk, { stream: true });
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop();
    let currentEvent = {};
    for (const raw of lines) {
      const line = raw.trimEnd();
      if (line === "") {
        this._handleEvent(currentEvent);
        currentEvent = {};
        continue;
      }
      if (line.startsWith("event: ")) currentEvent.event = line.slice(7);
      else if (line.startsWith("data: ")) currentEvent.data = (currentEvent.data || "") + line.slice(6) + "\n";
      else if (line.startsWith("id: ")) currentEvent.id = line.slice(4);
    }
    if (Object.keys(currentEvent).length) this._handleEvent(currentEvent);
  }

  _handleEvent(ev) {
    if (ev.data && ev.data.endsWith("\n")) ev.data = ev.data.slice(0, -1);
    if (ev.event === "endpoint" && ev.data) {
      const base = new URL(this.sseUrl);
      this.messageUrl = new URL(ev.data, `${base.protocol}//${base.host}`).href;
      return;
    }
    if (ev.event === "message" && ev.data) {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.id !== undefined && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
          else resolve(msg.result);
        }
      } catch (_) {}
    }
  }

  _startReading() {
    const loop = async () => {
      try {
        while (true) {
          const { done, value } = await this.reader.read();
          if (done) break;
          this._append(value);
        }
      } catch (_) {}
    };
    loop();
  }

  async call(method, params, timeoutMs = 60000) {
    const id = this.nextId++;
    const body = { jsonrpc: "2.0", id, method, params };
    const res = await fetch(this.messageUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok && res.status !== 202) {
      throw new Error(`POST ${method} failed: ${res.status} ${res.statusText}`);
    }
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`Timeout waiting for response to ${method} (${timeoutMs}ms)`));
        }
      }, timeoutMs);
    });
  }

  notify(method, params) {
    return fetch(this.messageUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

async function main() {
  console.error(`[a2a] Connecting SSE: ${SSE_URL}`);
  const client = new SseMcpClient(SSE_URL);
  await client.connect();
  console.error(`[a2a] Messages URL: ${client.messageUrl}`);

  await client.call("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "dlc-mimo-gallery-review", version: "1.0.0" },
  });
  await client.notify("notifications/initialized");

  console.error(`[a2a] Sending gallery review to MiMo (${MIMO_URL}), timeout ${TIMEOUT_MS}ms...`);
  const reviewResult = await client.call(
    "tools/call",
    {
      name: "send_message",
      arguments: {
        agent_url: MIMO_URL,
        message: REVIEW_PROMPT,
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
