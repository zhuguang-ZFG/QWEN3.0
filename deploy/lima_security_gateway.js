/**
 * LiMa Security Gateway — Cloudflare Worker
 * 前置鉴权、限流、路径白名单
 * 部署后绑定到 chat.donglicao.com，所有请求先过 Worker 再到 origin
 */

const ALLOWED_PATHS = [
  '/v1/',
  '/health',
  '/telegram/webhook',
  '/agent/',
  '/mcp/',
  '/fleet/',
];

const ADMIN_PATHS = ['/agent/', '/mcp/', '/fleet/'];

const RATE_LIMITS = {
  '/v1/': { rpm: 60, burst: 10 },
  '/agent/': { rpm: 30, burst: 5 },
  '/fleet/': { rpm: 60, burst: 10 },
  '/telegram/webhook': { rpm: 120, burst: 20 },
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/health') {
      return fetch(request);
    }

    const allowed = ALLOWED_PATHS.some(p => path.startsWith(p));
    if (!allowed && path !== '/') {
      return new Response('Not Found', { status: 404 });
    }

    const isAdmin = ADMIN_PATHS.some(p => path.startsWith(p));
    if (isAdmin) {
      const auth = request.headers.get('Authorization') || '';
      const token = auth.replace('Bearer ', '').trim();
      if (!token || token !== env.LIMA_ADMIN_TOKEN) {
        return new Response('Unauthorized', { status: 401 });
      }
    }

    if (path === '/telegram/webhook') {
      const secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token');
      if (!secret || secret !== env.TELEGRAM_WEBHOOK_SECRET) {
        return new Response('Forbidden', { status: 403 });
      }
    }

    if (request.body) {
      const size = parseInt(request.headers.get('Content-Length') || '0');
      if (size > 1048576) {
        return new Response('Payload Too Large', { status: 413 });
      }
    }

    return fetch(request);
  },
};
