/**
 * Kimi 本地代理服务 v2 (port 4504)
 * 支持: kimi, kimi-thinking, kimi-search, kimi-thinking-search
 * 增强: tool_calls 转发 + 对话历史 + 流式响应
 * Token 从 session 文件读取
 */
const http = require('http');
const https = require('https');
const fs = require('fs');

const PORT = 4504;
const SESSION_FILE = process.env.KIMI_SESSION_FILE || '/opt/lima-router/reverse_gateway_state/kimi_session.json';
const MODELS = {
  "kimi":                   {thinking: false, search: false},
  "kimi-thinking":          {thinking: true,  search: false},
  "kimi-search":            {thinking: false, search: true},
  "kimi-thinking-search":   {thinking: true,  search: true}
};

function getToken() {
  const paths = [SESSION_FILE, '/root/kimi_session.json', '/opt/lima-router/infra/kimi_session.json'];
  for (const p of paths) {
    try {
      if (fs.existsSync(p)) {
        const session = JSON.parse(fs.readFileSync(p, 'utf-8'));
        const token = session.authToken || session.token || session.access_token;
        if (token) { console.log('[Kimi] token loaded from', p); return token; }
      }
    } catch(e) { /* try next path */ }
  }
  throw new Error('No valid Kimi session found. Check SESSION_FILE paths.');
}

function kimiRequest(method, path, body, token) {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : '';
    const req = https.request({
      hostname: 'www.kimi.com', path, method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token,
        'Origin': 'https://kimi.moonshot.cn',
        'Referer': 'https://kimi.moonshot.cn/',
        'User-Agent': 'Mozilla/5.0'
      }
    }, (res) => {
      let result = '';
      res.on('data', c => result += c);
      res.on('end', () => {
        if (res.statusCode >= 400) {
          reject(new Error(`Kimi API ${res.statusCode}: ${result.substring(0, 200)}`));
        } else {
          resolve({ status: res.statusCode, body: result });
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(120000, () => { req.destroy(); reject(new Error('Kimi request timeout')); });
    if (payload) req.write(payload);
    req.end();
  });
}

// Extract messages from OpenAI format, preserving full conversation history
function extractMessages(parsed) {
  const msgs = parsed.messages || [];
  if (msgs.length === 0) return [{role: 'user', content: 'hi'}];

  // Build full message list for Kimi API
  const result = [];
  for (const m of msgs) {
    let content = '';
    if (typeof m.content === 'string') {
      content = m.content;
    } else if (Array.isArray(m.content)) {
      // Handle multimodal content arrays
      content = m.content
        .filter(c => c.type === 'text' || c.type === 'input_text')
        .map(c => c.text || '')
        .join('\n');
    }
    if (content) {
      // Kimi web chat API does not support 'system' role.
      // Convert system messages to user with a prefix so they are
      // still delivered to the model.
      let role = m.role || 'user';
      if (role === 'system') {
        role = 'user';
        content = '[System Instruction] ' + content;
      }
      result.push({role: role, content: content});
    }
  }
  return result.length > 0 ? result : [{role: 'user', content: 'hi'}];
}

// Convert OpenAI tools to Kimi internal format
function convertTools(openaiTools) {
  if (!Array.isArray(openaiTools) || openaiTools.length === 0) return null;
  return openaiTools.map(t => {
    if (t.type === 'function' && t.function) {
      return {
        type: 'function',
        function: {
          name: t.function.name,
          description: t.function.description || '',
          parameters: t.function.parameters || {}
        }
      };
    }
    return t;
  });
}

// Parse SSE stream for tool_calls and text
function parseStreamResponse(streamBody) {
  let content = '';
  const toolCalls = [];
  const toolCallMap = {}; // index -> {id, name, arguments}

  for (const line of streamBody.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('data:')) continue;

    const jsonStr = trimmed.substring(5).trim();
    if (!jsonStr || jsonStr === '[DONE]') continue;

    try {
      const d = JSON.parse(jsonStr);

      // Text completion
      if (d.event === 'cmpl' && d.text) {
        content += d.text;
      }

      // Tool call detection - Kimi may return tool_calls in various formats
      if (d.tool_calls && Array.isArray(d.tool_calls)) {
        for (const tc of d.tool_calls) {
          const idx = tc.index || 0;
          if (!toolCallMap[idx]) {
            toolCallMap[idx] = {
              id: tc.id || ('call_' + Math.random().toString(36).substr(2, 9)),
              type: 'function',
              function: { name: tc.function?.name || tc.name || '', arguments: '' }
            };
          }
          if (tc.function?.arguments) toolCallMap[idx].function.arguments += tc.function.arguments;
          if (tc.function?.name) toolCallMap[idx].function.name = tc.function.name;
          if (tc.id && !toolCallMap[idx].id.startsWith('call_')) toolCallMap[idx].id = tc.id;
        }
      }

      // Alternative: delta format
      if (d.choices && Array.isArray(d.choices)) {
        for (const choice of d.choices) {
          const delta = choice.delta || {};
          if (delta.content) content += delta.content;
          if (delta.tool_calls && Array.isArray(delta.tool_calls)) {
            for (const tc of delta.tool_calls) {
              const idx = tc.index || 0;
              if (!toolCallMap[idx]) {
                toolCallMap[idx] = {
                  id: tc.id || ('call_' + Math.random().toString(36).substr(2, 9)),
                  type: 'function',
                  function: { name: tc.function?.name || '', arguments: '' }
                };
              }
              if (tc.function?.arguments) toolCallMap[idx].function.arguments += tc.function.arguments;
              if (tc.function?.name) toolCallMap[idx].function.name = tc.function.name;
              if (tc.id) toolCallMap[idx].id = tc.id;
            }
          }
        }
      }
    } catch(e) {
      // Skipping malformed SSE line
    }
  }

  // Collect ordered tool calls
  for (let i = 0; i < Object.keys(toolCallMap).length; i++) {
    if (toolCallMap[i]) {
      try {
        // Validate JSON arguments
        JSON.parse(toolCallMap[i].function.arguments);
      } catch(e) {
        toolCallMap[i].function.arguments = '{}';
      }
      toolCalls.push(toolCallMap[i]);
    }
  }

  return { content: content.replace(/\[done\]$/i, '').trim(), toolCalls };
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');

  if (req.method === 'OPTIONS') {
    res.writeHead(204); res.end();
    return;
  }

  if (req.url === '/v1/models' && req.method === 'GET') {
    const data = Object.keys(MODELS).map(id => ({id, object: 'model', owned_by: 'moonshot'}));
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({object: 'list', data}));
    return;
  }

  if (req.url === '/v1/chat/completions' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const parsed = JSON.parse(body);
        const modelCfg = MODELS[parsed.model] || MODELS['kimi'];
        const messages = extractMessages(parsed);
        const tools = convertTools(parsed.tools);
        const toolChoice = parsed.tool_choice || (tools ? 'auto' : undefined);
        const token = getToken();

        // Create chat session
        const chatRes = await kimiRequest('POST', '/api/chat',
          {name: messages[0]?.content?.substring(0, 30) || 'q', is_example: false}, token);
        const chat = JSON.parse(chatRes.body);
        if (!chat.id) {
          res.writeHead(500, {'Content-Type': 'application/json'});
          res.end(JSON.stringify({error: 'create chat failed', detail: chat}));
          return;
        }

        // Build completion request with full conversation history and optional tools
        const completionBody = {
          messages: messages,
          refs: [],
          use_search: modelCfg.search,
          use_thinking: modelCfg.thinking
        };
        if (tools) {
          completionBody.tools = tools;
          if (toolChoice) completionBody.tool_choice = toolChoice;
        }

        console.log('[Kimi] sending completion with', messages.length, 'messages',
                    tools ? `+ ${tools.length} tools` : '');

        const msgRes = await kimiRequest('POST',
          `/api/chat/${chat.id}/completion/stream`, completionBody, token);

        const { content, toolCalls } = parseStreamResponse(msgRes.body);

        // Build OpenAI-compatible response
        const response = {
          id: 'kimi-' + Date.now(),
          object: 'chat.completion',
          created: Math.floor(Date.now() / 1000),
          model: parsed.model || 'kimi',
          choices: [{
            index: 0,
            message: {
              role: 'assistant',
              content: toolCalls.length > 0 ? null : content
            },
            finish_reason: toolCalls.length > 0 ? 'tool_calls' : 'stop'
          }],
          usage: {prompt_tokens: 0, completion_tokens: 0, total_tokens: 0}
        };

        if (toolCalls.length > 0) {
          response.choices[0].message.tool_calls = toolCalls;
          response.choices[0].message.content = content || null;
          console.log('[Kimi] tool_calls detected:', toolCalls.length);
        }

        res.writeHead(200, {'Content-Type': 'application/json'});
        res.end(JSON.stringify(response));
      } catch(e) {
        console.error('[Kimi] Error:', e.message);
        res.writeHead(500, {'Content-Type': 'application/json'});
        res.end(JSON.stringify({error: e.message}));
      }
    });
    return;
  }

  res.writeHead(404, {'Content-Type': 'text/plain'});
  res.end('Not Found');
});

server.listen(PORT, () => console.log(`[Kimi Proxy v2] Running on port ${PORT}`));
