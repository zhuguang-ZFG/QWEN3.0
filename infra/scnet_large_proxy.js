/**
 * SCNet 大上下文代理 (port 4505)
 * OpenAI 兼容接口，自动处理大文件上传
 * - 输入 ≤ 50K: 直接走 content
 * - 输入 > 50K: 上传文件到 OSS → textFile 引用
 * 最大支持 ~950K 字符 (~237K tokens)
 */
const http = require('http');
const https = require('https');
const crypto = require('crypto');
const fs = require('fs');

const PORT = 4505;
const SESSION_FILE = 'D:/ollama_server/scnet_session.json';
const SCNET_HOST = 'www.scnet.cn';
const CONTENT_LIMIT = 45000;
const MODELS = {
  'deepseek-v4-flash': { id: 520, maxFile: 950000 },
  'deepseek-v4-pro': { id: 510, maxFile: 500000 },
  'qwen3-235b': { id: 120, maxFile: 0 },
  'qwen3-30b': { id: 17, maxFile: 60000 },
  'minimax-m25': { id: 410, maxFile: 0 }
};

function getCookies() {
  const session = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
  return session.cookies.map(c => c.name + '=' + c.value).join('; ');
}

function scnetReq(method, path, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : '';
    const req = https.request({
      hostname: SCNET_HOST, path, method,
      headers: { 'Content-Type': 'application/json', 'Cookie': getCookies(),
        'Origin': 'https://www.scnet.cn', 'Referer': 'https://www.scnet.cn/ui/chatbot/' }
    }, res => { let d = ''; res.on('data', c => d += c); res.on('end', () => resolve(d)); });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

function uploadToOSS(content) {
  return new Promise(async (resolve, reject) => {
    try {
      const sigResp = await scnetReq('GET', '/acx/chatbot/file/sso/form/signature');
      const sig = JSON.parse(sigResp).data;
      const hash = crypto.createHash('md5').update(String(Date.now() + Math.random())).digest('hex');
      const fileName = hash + '.txt';
      const key = sig.dir + '/' + fileName;
      const ossUrl = sig.host + '/' + key;

      const boundary = '----FB' + Math.random().toString(36).substr(2);
      const fields = { key, policy: sig.policy, OSSAccessKeyId: sig.accessid, signature: sig.signature, 'x-oss-object-acl': 'public-read' };
      let form = '';
      for (const [k, v] of Object.entries(fields)) form += '--' + boundary + '\r\nContent-Disposition: form-data; name="' + k + '"\r\n\r\n' + v + '\r\n';
      form += '--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="' + fileName + '"\r\nContent-Type: text/plain\r\n\r\n';
      const buf = Buffer.concat([Buffer.from(form), Buffer.from(content), Buffer.from('\r\n--' + boundary + '--\r\n')]);

      const url = new URL(sig.host);
      const req = https.request({ hostname: url.hostname, path: '/', method: 'POST',
        headers: { 'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Content-Length': buf.length }
      }, res => {
        if (res.statusCode === 204 || res.statusCode === 200) resolve({ ossUrl, fileName, size: content.length });
        else reject(new Error('OSS upload failed: ' + res.statusCode));
      });
      req.on('error', reject);
      req.write(buf);
      req.end();
    } catch (e) { reject(e); }
  });
}

function chatWithSCNet(content, textFile, modelId) {
  return new Promise(async (resolve, reject) => {
    try {
      const body = { conversationId: '', content, thinkingEnable: false, onlineEnable: false,
        modelId, textFile: textFile || [], imageFile: [], autoRun: 0, clusterId: '' };
      const resp = await scnetReq('POST', '/acx/chatbot/v1/chat/completion', body);
      let reply = '';
      for (const line of resp.split('\n')) {
        if (line.startsWith('data:')) {
          try { const d = JSON.parse(line.substring(5)); if (d.content && d.content !== '[done]') reply += d.content; } catch (e) {}
        }
      }
      resolve(reply);
    } catch (e) { reject(e); }
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', '*');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  if (req.url === '/v1/models') {
    const data = Object.keys(MODELS).map(id => ({ id, object: 'model', owned_by: 'scnet' }));
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ object: 'list', data }));
    return;
  }

  if (req.url === '/v1/chat/completions' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const parsed = JSON.parse(body);
        const modelCfg = MODELS[parsed.model] || MODELS['deepseek-v4-flash'];
        const modelId = modelCfg.id;
        const maxFile = modelCfg.maxFile;
        const msgs = parsed.messages || [];
        const fullText = msgs.map(m => (typeof m.content === 'string' ? m.content : '')).join('\n\n');
        let question = msgs.filter(m => m.role === 'user').pop()?.content || '';
        let textFile = [];

        if (fullText.length > CONTENT_LIMIT && maxFile > 0) {
          const fileContent = msgs.map(m => `[${m.role}]\n${m.content}`).join('\n\n---\n\n');
          if (fileContent.length > maxFile) {
            res.writeHead(413, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: `Input ${fileContent.length} chars exceeds model limit ${maxFile}` }));
            return;
          }
          question = question.length > CONTENT_LIMIT
            ? '请根据附件中的对话上下文，回答最后一个用户问题。'
            : question;
          const uploaded = await uploadToOSS(fileContent);
          textFile = [{ name: uploaded.fileName, path: uploaded.ossUrl, size: uploaded.size, type: 'text/plain' }];
        } else if (fullText.length > CONTENT_LIMIT && maxFile === 0) {
          question = fullText.substring(fullText.length - CONTENT_LIMIT);
        }

        const reply = await chatWithSCNet(question, textFile, modelId);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          id: 'scnet-' + Date.now(), object: 'chat.completion',
          created: Math.floor(Date.now() / 1000), model: parsed.model || 'deepseek-v4-flash',
          choices: [{ index: 0, message: { role: 'assistant', content: reply }, finish_reason: 'stop' }],
          usage: { prompt_tokens: Math.round(fullText.length / 4), completion_tokens: Math.round(reply.length / 4), total_tokens: 0 }
        }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }
  res.writeHead(404); res.end('Not Found');
});

server.listen(PORT, () => console.log(`[SCNet Large] Running on port ${PORT} (max ~950K chars)`));
