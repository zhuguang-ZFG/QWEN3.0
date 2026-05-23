// Cloudflare Worker: Telegram API 代理
// 部署到 tg.zhuguang.ccwu.cc
// 用法: POST https://tg.zhuguang.ccwu.cc/bot{token}/{method}
//       → 转发到 https://api.telegram.org/bot{token}/{method}

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // 只允许 /bot 开头的路径
    if (!url.pathname.startsWith('/bot')) {
      return new Response('Not found', { status: 404 });
    }

    // 构建 Telegram API URL
    const telegramUrl = `https://api.telegram.org${url.pathname}${url.search}`;

    // 转发请求
    const init = {
      method: request.method,
      headers: {
        'Content-Type': request.headers.get('Content-Type') || 'application/json',
      },
    };

    if (request.method === 'POST') {
      init.body = await request.text();
    }

    try {
      const response = await fetch(telegramUrl, init);
      const body = await response.text();
      return new Response(body, {
        status: response.status,
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (e) {
      return new Response(JSON.stringify({ ok: false, error: e.message }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  },
};
