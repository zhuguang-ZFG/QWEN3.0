/**
 * heck.ai → OpenAI 兼容接口
 * 免费 GPT-4.1-mini，无需 Key/登录
 */
const UPSTREAM = "https://api.heckai.weight-wave.com/api/ha/v1";
const CH = {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"*","Access-Control-Allow-Methods":"*","Content-Type":"application/json"};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, {headers: CH});

    if (url.pathname === "/v1/models") {
      return new Response(JSON.stringify({object:"list",data:[
        {id:"gpt-4.1-mini",object:"model",created:Date.now(),owned_by:"heck.ai"}
      ]}), {headers: CH});
    }

    if (url.pathname === "/v1/chat/completions" && request.method === "POST") {
      const body = await request.json();
      const question = (body.messages || []).filter(m => m.role === "user").pop()?.content || "";
      const sessionId = crypto.randomUUID();

      // Create session
      await fetch(`${UPSTREAM}/session/create`, {
        method: "POST", headers: {"Content-Type":"application/json","Origin":"https://www.heck.ai","Referer":"https://www.heck.ai/"},
        body: JSON.stringify({title: question.substring(0, 30)})
      }).catch(()=>{});

      // Send chat
      const res = await fetch(`${UPSTREAM}/chat`, {
        method: "POST",
        headers: {"Content-Type":"application/json","Origin":"https://www.heck.ai","Referer":"https://www.heck.ai/","User-Agent":"Mozilla/5.0"},
        body: JSON.stringify({
          model: "openai/gpt-4.1-mini",
          question: question,
          language: "English",
          sessionId: sessionId,
          previousQuestion: null,
          previousAnswer: null,
          imgUrls: [],
          superSmartMode: false
        })
      });

      // Parse SSE response
      const text = await res.text();
      let content = "";
      for (const line of text.split("\n")) {
        if (line.startsWith("data: ") && !line.includes("[ANSWER_DONE]") && !line.includes("[RELATE_Q") && !line.includes("[ERROR]")) {
          content += line.substring(6);
        }
      }
      content = content.trim();

      return new Response(JSON.stringify({
        id: "heck-" + Date.now(),
        object: "chat.completion",
        created: Math.floor(Date.now()/1000),
        model: "gpt-4.1-mini",
        choices: [{index:0, message:{role:"assistant", content}, finish_reason:"stop"}],
        usage: {prompt_tokens:0, completion_tokens:0, total_tokens:0}
      }), {headers: CH});
    }

    return new Response("Not Found", {status:404});
  }
};
