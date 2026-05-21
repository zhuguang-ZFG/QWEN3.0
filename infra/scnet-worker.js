/**
 * 国家超算互联网平台 (scnet.cn) → OpenAI 兼容接口
 * 免费 5 模型 (Qwen3-235B, DeepSeek-V4-Pro 等), 无需 Key/登录/翻墙
 * 自动分段: 超过 45000 字符时分多轮发送, 用 conversationId 保持上下文
 */
const UPSTREAM = "https://www.scnet.cn/acx/chatbot/v1/chat/completion";
const MODELS = {
  "qwen3-30b": 17,
  "minimax-m2.5": 410,
  "qwen3-235b": 120,
  "deepseek-v4-flash": 520,
  "deepseek-v4-pro": 510
};
const CHUNK_SIZE = 40000;
const CH = {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"*",
  "Access-Control-Allow-Methods":"*","Content-Type":"application/json"};

async function sendToScnet(content, modelId, conversationId) {
  const res = await fetch(UPSTREAM, {
    method: "POST",
    headers: {"Content-Type":"application/json",
      "Origin":"https://www.scnet.cn",
      "Referer":"https://www.scnet.cn/ui/chatbot/"},
    body: JSON.stringify({
      conversationId, content,
      thinkingEnable: false, onlineEnable: false,
      modelId, textFile: [], imageFile: [], autoRun: 0, clusterId: ""
    })
  });
  const text = await res.text();
  let reply = "", convId = conversationId;
  for (const line of text.split("\n")) {
    if (line.startsWith("data:")) {
      try {
        const d = JSON.parse(line.substring(5));
        if (d.conversationId) convId = d.conversationId;
        if (d.content && d.content !== "[done]") reply += d.content;
      } catch(e) {}
    }
  }
  return { reply: reply.replace(/\[done\]$/, "").trim(), convId };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null,{headers:CH});

    if (url.pathname === "/v1/chat/completions" && request.method === "POST") {
      const body = await request.json();
      const modelId = MODELS[body.model] || 17;
      const msgs = body.messages || [];
      const fullText = msgs.map(m => `[${m.role}]: ${m.content}`).join("\n");

      let content = "";
      if (fullText.length <= CHUNK_SIZE) {
        const r = await sendToScnet(fullText, modelId, "");
        content = r.reply;
      } else {
        const chunks = [];
        for (let i = 0; i < fullText.length; i += CHUNK_SIZE) {
          chunks.push(fullText.slice(i, i + CHUNK_SIZE));
        }
        let convId = "";
        for (let i = 0; i < chunks.length; i++) {
          const isLast = i === chunks.length - 1;
          const prefix = isLast ? "" : `[Part ${i+1}/${chunks.length}]\n`;
          const suffix = isLast
            ? "\n\nNow answer based on ALL parts above."
            : "\n\n[Say OK and wait for next part]";
          const r = await sendToScnet(prefix + chunks[i] + suffix, modelId, convId);
          convId = r.convId;
          if (isLast) content = r.reply;
        }
      }

      return new Response(JSON.stringify({
        id: "scnet-" + Date.now(),
        object: "chat.completion",
        created: Math.floor(Date.now()/1000),
        model: body.model || "qwen3-30b",
        choices: [{index:0,message:{role:"assistant",content},finish_reason:"stop"}],
        usage: {prompt_tokens:0,completion_tokens:0,total_tokens:0}
      }), {headers: CH});
    }
    return new Response("Not Found", {status:404});
  }
};
