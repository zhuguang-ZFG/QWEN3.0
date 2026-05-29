/**
 * Kimi 本地代理服务 (port 4504)
 * 支持 4 个模型: kimi, kimi-thinking, kimi-agent, kimi-agent-ultra
 * Token 通过 kimi_refresh.js 定时刷新
 */
const http = require('http');
const https = require('https');
const fs = require('fs');

const PORT = 4504;
const SESSION_FILE = 'D:/ollama_server/kimi_session.json';
const MODELS = {
  "kimi": {thinking: false, search: false},
  "kimi-thinking": {thinking: true, search: false},
  "kimi-search": {thinking: false, search: true},
  "kimi-thinking-search": {thinking: true, search: true}
};

function getToken() {
  const session = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
  return session.authToken;
}

function kimiPost(path, body, token) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = https.request({
      hostname: 'www.kimi.com', path, method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token,
        'Origin': 'https://kimi.moonshot.cn',
        'Referer': 'https://kimi.moonshot.cn/'
      }
    }, (res) => {
      let result = '';
      res.on('data', c => result += c);
      res.on('end', () => resolve({ status: res.statusCode, body: result }));
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', '*');
  if (req.url === '/v1/models' && req.method === 'GET') {
    const data = Object.keys(MODELS).map(id => ({id, object:"model", owned_by:"moonshot"}));
    res.writeHead(200, {'Content-Type':'application/json'});
    res.end(JSON.stringify({object:"list", data}));
    return;
  }

  if (req.url === '/v1/chat/completions' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const parsed = JSON.parse(body);
        const modelCfg = MODELS[parsed.model] || MODELS["kimi"];
        const msgs = parsed.messages || [];
        const question = msgs.filter(m => m.role === "user").pop()?.content || "";
        const token = getToken();

        const chatRes = await kimiPost('/api/chat', {name:'q', is_example:false}, token);
        const chat = JSON.parse(chatRes.body);
        if (!chat.id) { res.writeHead(500); res.end(JSON.stringify({error:'create chat failed', detail: chat})); return; }

        const msgRes = await kimiPost(`/api/chat/${chat.id}/completion/stream`,
          {messages:[{role:'user',content:question}], refs:[], use_search:modelCfg.search, use_thinking:modelCfg.thinking}, token);
        let content = '';
        for (const line of msgRes.body.split('\n')) {
          if (line.startsWith('data: ')) {
            try { const d = JSON.parse(line.substring(6)); if (d.event==='cmpl'&&d.text) content+=d.text; } catch(e){}
          }
        }

        res.writeHead(200, {'Content-Type':'application/json'});
        res.end(JSON.stringify({
          id: 'kimi-'+Date.now(), object:'chat.completion',
          created: Math.floor(Date.now()/1000), model: parsed.model||'kimi',
          choices: [{index:0, message:{role:'assistant',content}, finish_reason:'stop'}],
          usage: {prompt_tokens:0, completion_tokens:0, total_tokens:0}
        }));
      } catch(e) {
        res.writeHead(500);
        res.end(JSON.stringify({error: e.message}));
      }
    });
    return;
  }
  res.writeHead(404); res.end('Not Found');
});

server.listen(PORT, () => console.log(`[Kimi Proxy] Running on port ${PORT}`));
