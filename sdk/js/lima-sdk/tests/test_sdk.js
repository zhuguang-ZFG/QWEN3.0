import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { LiMaClient, LiMaAPIError } from "../src/index.js";

const API_KEY = "sk-test";

/** @type {http.Server|null} */
let server = null;
let baseUrl = "";

/** @type {Record<string, (req: http.IncomingMessage, res: http.ServerResponse) => void>} */
const routes = {
  "POST /v1/chat/completions": (req, res) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      const payload = JSON.parse(body);
      if (payload.stream) {
        res.writeHead(200, { "Content-Type": "text/event-stream" });
        res.write('data: {"choices":[{"delta":{"content":"hi"}}]}\n');
        res.write('data: {"choices":[{"delta":{"content":"!"}}]}\n');
        res.write("data: [DONE]\n\n");
        res.end();
      } else {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ id: "chat-1", choices: [{ message: { role: "assistant", content: "hello" } }] }));
      }
    });
  },
  "POST /v1/images/generations": (_req, res) => {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ data: [{ url: "https://example.com/img.png" }] }));
  },
  "GET /device/v1/app/devices": (_req, res) => {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ devices: [{ deviceId: "d1" }], count: 1 }));
  },
  "GET /device/v1/app/devices/d1/status": (_req, res) => {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ online: true }));
  },
  "POST /device/v1/app/devices/d1/tasks": (_req, res) => {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ taskId: "t1" }));
  },
  "GET /device/v1/app/tasks/t1": (_req, res) => {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ taskId: "t1", status: "running" }));
  },
  "GET /device/v1/app/assets": (_req, res) => {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ assets: [{ assetId: "a1" }], total: 1, limit: 20, offset: 0 }));
  },
  "POST /device/v1/app/assets": (_req, res) => {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ assetId: "a2" }));
  },
  "GET /device/v1/app/devices/missing": (_req, res) => {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: { message: "not found", type: "not_found" } }));
  },
};

before(async () => {
  server = http.createServer((req, res) => {
    const key = `${req.method} ${req.url?.split("?")[0] ?? ""}`;
    const handler = routes[key];
    if (handler) {
      handler(req, res);
    } else {
      res.writeHead(404);
      res.end("not found");
    }
  });
  await new Promise((resolve) => server?.listen(0, "127.0.0.1", resolve));
  const addr = server?.address();
  baseUrl = typeof addr === "object" && addr ? `http://127.0.0.1:${addr.port}` : "";
});

after(async () => {
  await new Promise((resolve) => server?.close(resolve));
});

describe("LiMaClient", () => {
  it("chat completion", async () => {
    const client = new LiMaClient(API_KEY, { baseUrl });
    const resp = await client.chat.create({
      model: "lima-1.3",
      messages: [{ role: "user", content: "hi" }],
    });
    assert.equal(resp.choices[0].message.content, "hello");
  });

  it("chat completion stream", async () => {
    const client = new LiMaClient(API_KEY, { baseUrl });
    const stream = await client.chat.create({
      model: "lima-1.3",
      messages: [{ role: "user", content: "hi" }],
      stream: true,
    });
    const chunks = [];
    for await (const chunk of stream) {
      chunks.push(chunk);
    }
    assert.equal(chunks.length, 2);
    assert.equal(chunks[0].choices[0].delta.content, "hi");
  });

  it("images generate", async () => {
    const client = new LiMaClient(API_KEY, { baseUrl });
    const resp = await client.images.generate({ model: "dall-e-3", prompt: "a cat" });
    assert.equal(resp.data[0].url, "https://example.com/img.png");
  });

  it("devices list and status", async () => {
    const client = new LiMaClient(API_KEY, { baseUrl });
    const { devices } = await client.devices.list();
    assert.equal(devices[0].deviceId, "d1");
    const status = await client.devices.status("d1");
    assert.equal(status.online, true);
  });

  it("devices create and get task", async () => {
    const client = new LiMaClient(API_KEY, { baseUrl });
    const task = await client.devices.createTask("d1", { text: "hello" });
    assert.equal(task.taskId, "t1");
    const fetched = await client.devices.getTask("t1");
    assert.equal(fetched.status, "running");
  });

  it("assets list and create", async () => {
    const client = new LiMaClient(API_KEY, { baseUrl });
    const { assets } = await client.assets.list();
    assert.equal(assets[0].assetId, "a1");
    const created = await client.assets.create({ title: "cat", category: "svg", content: "<svg/>" });
    assert.equal(created.assetId, "a2");
  });

  it("api error", async () => {
    const client = new LiMaClient(API_KEY, { baseUrl });
    await assert.rejects(async () => client.devices.get("missing"), (err) => {
      assert.ok(err instanceof LiMaAPIError);
      assert.equal(err.statusCode, 404);
      assert.match(err.message, /not found/);
      return true;
    });
  });
});
