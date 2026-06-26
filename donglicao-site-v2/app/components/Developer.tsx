"use client";

import Link from "next/link";
import { useState } from "react";

const snippets = [
  {
    lang: "python",
    label: "Python",
    code: `import openai

client = openai.OpenAI(
    base_url="https://chat.donglicao.com/v1",
    api_key="sk-your-api-key",
)

resp = client.chat.completions.create(
    model="lima-1.3",
    messages=[{"role": "user", "content": "画一只在月球上的猫"}],
)
print(resp.choices[0].message.content)`,
  },
  {
    lang: "curl",
    label: "cURL",
    code: `curl -X POST https://chat.donglicao.com/v1/chat/completions \\
  -H "Authorization: Bearer sk-your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "lima-1.3",
    "messages": [{"role": "user", "content": "画一只在月球上的猫"}]
  }'`,
  },
  {
    lang: "javascript",
    label: "JavaScript",
    code: `import { LiMaClient } from "lima-sdk";

const client = new LiMaClient("sk-your-api-key");

const resp = await client.chat.create({
  model: "lima-1.3",
  messages: [{ role: "user", content: "画一只在月球上的猫" }],
});
console.log(resp.choices[0].message.content);`,
  },
  {
    lang: "go",
    label: "Go",
    code: `package main

import (
    "context"
    "fmt"
    "github.com/donglicao/lima-sdk-go/lima"
)

func main() {
    client := lima.NewClient(lima.ClientConfig{
        APIKey: "sk-your-api-key",
    })
    resp, err := client.Chat.Create(context.Background(), lima.CreateChatCompletionRequest{
        Model: "lima-1.3",
        Messages: []lima.ChatMessage{{Role: "user", Content: "画一只在月球上的猫"}},
    })
    if err != nil { panic(err) }
    fmt.Println(resp.Choices[0].Message.Content)
}`,
  },
];

export default function Developer() {
  const [active, setActive] = useState("python");
  const current = snippets.find((s) => s.lang === active) || snippets[0];

  return (
    <section id="developer" className="px-6 py-20">
      <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-2">
        <div className="space-y-6">
          <h2 className="text-3xl font-bold text-slate-50 md:text-4xl">
            面向开发者的
            <br />
            <span className="text-cyan-400">开放接口</span>
          </h2>
          <p className="text-lg text-slate-400">
            兼容 OpenAI 格式的 API，支持设备控制、内容生成、多模型路由。一行代码接入 LiMa 云端能力。
          </p>
          <div className="flex flex-wrap gap-4">
            <a
              href="https://chat.donglicao.com"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center gap-2 rounded-full bg-cyan-500 px-6 py-3 font-semibold text-white hover:bg-cyan-400"
            >
              获取 API Key
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </a>
            <Link
              href="/developer/playground/"
              className="inline-flex items-center gap-2 rounded-full border border-white/10 px-6 py-3 font-semibold text-slate-200 hover:border-cyan-500/50 hover:text-cyan-400"
            >
              API Playground
            </Link>
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0d1117]">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
            <div className="flex gap-2">
              <span className="h-3 w-3 rounded-full bg-red-500" />
              <span className="h-3 w-3 rounded-full bg-yellow-500" />
              <span className="h-3 w-3 rounded-full bg-green-500" />
            </div>
            <div className="flex gap-1">
              {snippets.map((s) => (
                <button
                  key={s.lang}
                  onClick={() => setActive(s.lang)}
                  className={`rounded px-3 py-1 text-xs ${
                    active === s.lang
                      ? "bg-white/10 text-slate-100"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <pre className="overflow-x-auto p-4 text-sm leading-relaxed text-slate-300">
            <code>{current.code}</code>
          </pre>
        </div>
      </div>
    </section>
  );
}
