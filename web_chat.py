#!/usr/bin/env python3
"""
Web Chat UI for red V1-Flash Router.
Seamless model routing — user never sees model switching.
Run: python web_chat.py → http://localhost:8080
"""

import http.server
import json
import os
import sys
from urllib.parse import urlparse
from html import escape

sys.path.insert(0, os.path.dirname(__file__))
from model_router import route_query, ALL_DOMAIN_KEYWORDS

chat_histories = {}

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>red V1-Flash | 动力巢科技</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"Microsoft YaHei",sans-serif;background:#0a0a0a;color:#e0e0e0;height:100vh;display:flex;flex-direction:column}
header{background:linear-gradient(135deg,#1a0000,#0a0a2e);padding:12px 24px;border-bottom:1px solid #333;display:flex;align-items:center;gap:16px}
header h1{color:#ff4444;font-size:18px}
header span{color:#666;font-size:13px}
#messages{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px}
.msg{max-width:800px;padding:12px 16px;border-radius:12px;line-height:1.6}
.msg.user{align-self:flex-end;background:#1a3a5c;border:1px solid #2a5a8c}
.msg.assistant{align-self:flex-start;background:#1a1a1a;border:1px solid #333}
.msg .meta{font-size:11px;color:#555;margin-bottom:6px}
.msg pre{background:#0d0d0d;padding:12px;border-radius:8px;overflow-x:auto;margin:8px 0;font-size:13px}
.msg code{font-family:'Fira Code','Cascadia Code',monospace}
#input-area{padding:16px 24px;background:#111;border-top:1px solid #333;display:flex;gap:12px}
#input-area input{flex:1;background:#1a1a1a;border:1px solid #444;color:#e0e0e0;padding:12px 16px;border-radius:8px;font-size:15px;outline:none}
#input-area input:focus{border-color:#ff4444}
#input-area button{background:#ff4444;color:#fff;border:none;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:15px}
#input-area button:hover{background:#ff6666}
#input-area button:disabled{background:#444;cursor:not-allowed}
.typing{color:#666;font-style:italic}
</style>
</head>
<body>
<header>
  <h1>&#9776; red V1-Flash</h1>
  <span>深圳市动力巢科技</span>
</header>
<div id="messages"></div>
<div id="input-area">
  <input id="query" placeholder="输入问题..." autocomplete="off">
  <button id="send" onclick="send()">发送</button>
</div>
<script>
const sessionId=Math.random().toString(36).slice(2);
const messages=document.getElementById('messages');
const query=document.getElementById('query');
const sendBtn=document.getElementById('send');
query.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});

function addMsg(role,text,meta=''){
  const div=document.createElement('div');
  div.className='msg '+role;
  const fmt=text.replace(/```(\w*)\n([\s\S]*?)```/g,'<pre><code>$2</code></pre>').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\n/g,'<br>');
  div.innerHTML='<div class="meta">'+meta+'</div>'+fmt;
  messages.appendChild(div);
  messages.scrollTop=messages.scrollHeight;
}

async function send(){
  const q=query.value.trim();
  if(!q)return;
  query.value='';
  sendBtn.disabled=true;
  addMsg('user',q);
  const typing=document.createElement('div');
  typing.className='msg assistant';
  typing.innerHTML='<span class="typing">思考中...</span>';
  messages.appendChild(typing);
  messages.scrollTop=messages.scrollHeight;
  try{
    const resp=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q,session:sessionId})});
    const data=await resp.json();
    messages.removeChild(typing);
    // 路由信息对用户隐藏，统一显示品牌
    addMsg('assistant',data.response,'red V1-Flash');
  }catch(e){
    messages.removeChild(typing);
    addMsg('assistant','请求失败: '+e.message);
  }
  sendBtn.disabled=false;
  query.focus();
}
</script>
</body>
</html>"""


class ChatHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            query_text = body.get("query", "")
            session = body.get("session", "default")

            history = chat_histories.get(session, [])
            result = route_query(query_text, history)
            chat_histories[session] = history + [
                {"role": "user", "content": query_text},
                {"role": "assistant", "content": result["response"]},
            ]
            if len(chat_histories[session]) > 20:
                chat_histories[session] = chat_histories[session][-20:]

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = 8080
    server = http.server.HTTPServer(("", port), ChatHandler)
    print(f"red V1-Flash Web UI running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    server.serve_forever()
