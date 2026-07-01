/**
 * LiMa chat-router — Cloudflare Worker 透明兜底/灰度
 *
 * 路由规则：
 *   - 仅拦截 chat.donglicao.com/v1/chat/completions* 的 POST 请求。
 *   - 无 Authorization 头（匿名）的聊天请求优先转发到阿里云 pilot（aliyun.donglicao.com）。
 *   - 其余请求（含带 key、非 chat completions、OPTIONS 等）回源到 JDCloud（origin-chat.donglicao.com）。
 *   - pilot 返回 429/5xx/408 时自动回源兜底。
 *
 * 注意：Worker 不解析请求体，仅按 path + Authorization 存在性做粗分流；
 *       vision/tools/image 等更细规则仍由前端保证。
 */

const PILOT_PATH = "/v1/chat/completions";
const DEFAULT_ORIGIN = "https://origin-chat.donglicao.com";
const PILOT_ORIGIN = "https://aliyun.donglicao.com";
const FALLBACK_STATUSES = new Set([408, 429, 500, 502, 503, 504]);

function isPilotCandidate(request, url) {
  if (request.method !== "POST") return false;
  if (!url.pathname.startsWith(PILOT_PATH)) return false;
  const auth = request.headers.get("Authorization") || "";
  // 任何看起来像 Bearer key 的请求都回源；空值或非法值视为匿名。
  return !auth.startsWith("Bearer ");
}

function passHeaders(request) {
  const headers = new Headers(request.headers);
  // Host 由 fetch 根据目标 URL 自动设置，无需保留原 Host。
  headers.delete("Host");
  headers.delete("cf-worker");
  return headers;
}

function annotateResponse(response, backend, fallback = false) {
  const h = new Headers(response.headers);
  h.set("X-Lima-Backend", backend);
  if (fallback) {
    h.set("X-Lima-Fallback", "true");
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: h,
  });
}

async function proxyTo(request, url, origin) {
  const target = new URL(url.pathname + url.search, origin);
  const init = {
    method: request.method,
    headers: passHeaders(request),
    body: request.body,
    redirect: "manual",
  };
  return fetch(new Request(target, init));
}

function handleCors(request) {
  const origin = request.headers.get("Origin") || "*";
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Requested-With",
      "Access-Control-Max-Age": "86400",
    },
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return handleCors(request);
    }

    if (!isPilotCandidate(request, url)) {
      const resp = await proxyTo(request, url, DEFAULT_ORIGIN);
      return annotateResponse(resp, "jdcloud");
    }

    // 需要为可能的兜底保留一份 body 副本。
    const bodyText = await request.text();
    const headers = passHeaders(request);

    const pilotReq = new Request(new URL(url.pathname + url.search, PILOT_ORIGIN), {
      method: "POST",
      headers,
      body: bodyText,
      redirect: "manual",
    });

    let resp = await fetch(pilotReq);
    if (FALLBACK_STATUSES.has(resp.status)) {
      const originReq = new Request(new URL(url.pathname + url.search, DEFAULT_ORIGIN), {
        method: "POST",
        headers,
        body: bodyText,
        redirect: "manual",
      });
      resp = await fetch(originReq);
      return annotateResponse(resp, "jdcloud", true);
    }

    return annotateResponse(resp, "aliyun");
  },
};
