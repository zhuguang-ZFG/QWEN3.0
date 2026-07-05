/**
 * LiMa chat-router — Cloudflare Worker
 *
 * 路由规则：
 *   - 仅拦截 chat.donglicao.com/v1/chat/completions* 的请求。
 *   - 所有请求统一回源到 JDCloud（origin-chat.donglicao.com）。
 *   - OPTIONS 预检由 Worker 直接返回 CORS 头。
 *
 * 历史：曾把匿名 chat 分流到阿里云 pilot（aliyun.donglicao.com），
 *       pilot 链路 2026-07-05 退役（入站流量为 0），分流逻辑已移除。
 */

const DEFAULT_ORIGIN = "https://origin-chat.donglicao.com";

function passHeaders(request) {
  const headers = new Headers(request.headers);
  // Host 由 fetch 根据目标 URL 自动设置，无需保留原 Host。
  headers.delete("Host");
  headers.delete("cf-worker");
  return headers;
}

function annotateResponse(response, backend) {
  const h = new Headers(response.headers);
  h.set("X-Lima-Backend", backend);
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

    const resp = await proxyTo(request, url, DEFAULT_ORIGIN);
    return annotateResponse(resp, "jdcloud");
  },
};
