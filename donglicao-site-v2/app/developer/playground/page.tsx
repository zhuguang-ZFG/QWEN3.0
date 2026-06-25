"use client";

import { useEffect, useState } from "react";
import Navbar from "../../components/Navbar";
import Footer from "../../components/Footer";

const endpoints = [
  { value: "/v1/chat/completions", label: "Chat Completions", method: "POST" },
  { value: "/v1/images/generations", label: "Images", method: "POST" },
  { value: "/v1/models", label: "Models", method: "GET" },
];

export default function PlaygroundPage() {
  const [apiKey, setApiKey] = useState("");
  const [endpoint, setEndpoint] = useState("/v1/chat/completions");
  const [model, setModel] = useState("lima-1.3");
  const [prompt, setPrompt] = useState("你好，请介绍一下 LiMa 量子星云系统。");
  const [baseUrl, setBaseUrl] = useState("https://chat.donglicao.com");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const saved = localStorage.getItem("lima_playground_key");
    if (saved) setApiKey(saved);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResponse("");
    setError("");
    localStorage.setItem("lima_playground_key", apiKey);

    try {
      const selected = endpoints.find((ep) => ep.value === endpoint)!;
      let body: unknown;
      if (endpoint === "/v1/chat/completions") {
        body = { model, messages: [{ role: "user", content: prompt }] };
      } else if (endpoint === "/v1/images/generations") {
        body = { model, prompt, size: "1024x1024", n: 1 };
      }

      const res = await fetch(`${baseUrl}${endpoint}`, {
        method: selected.method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      let data: unknown;
      try {
        data = await res.json();
      } catch {
        data = { raw: await res.text() };
      }
      if (!res.ok) {
        setError(`HTTP ${res.status}: ${JSON.stringify(data, null, 2)}`);
      } else {
        setResponse(JSON.stringify(data, null, 2));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <main id="main" className="flex-1 px-6 pt-32 pb-20">
        <div className="mx-auto max-w-4xl">
          <div className="mb-8 text-center">
            <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Developer</div>
            <h1 className="text-3xl font-bold text-slate-50 md:text-4xl">API Playground</h1>
            <p className="mt-3 text-slate-400">在浏览器中直接测试 LiMa API。</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6 rounded-2xl border border-white/10 bg-white/[0.03] p-6">
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">Base URL</label>
                <input
                  type="url"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-4 py-2 text-slate-200 outline-none focus:border-cyan-500"
                  required
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-xxx"
                  className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-4 py-2 text-slate-200 outline-none focus:border-cyan-500"
                  required
                />
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">Endpoint</label>
                <select
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-4 py-2 text-slate-200 outline-none focus:border-cyan-500"
                >
                  {endpoints.map((ep) => (
                    <option key={ep.value} value={ep.value}>
                      {ep.label} — {ep.method} {ep.value}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">Model</label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-4 py-2 text-slate-200 outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {endpoint !== "/v1/models" && (
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">Prompt / Content</label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={4}
                  className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-4 py-2 text-slate-200 outline-none focus:border-cyan-500"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="rounded-full bg-cyan-500 px-6 py-2.5 font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-60"
            >
              {loading ? "请求中..." : "发送请求"}
            </button>
          </form>

          {error && (
            <div className="mt-6 overflow-x-auto rounded-xl border border-red-500/30 bg-red-500/10 p-4">
              <pre className="whitespace-pre-wrap text-sm text-red-200">{error}</pre>
            </div>
          )}

          {response && (
            <div className="mt-6 overflow-x-auto rounded-xl border border-cyan-500/20 bg-[#0d1117] p-4">
              <pre className="text-sm leading-relaxed text-slate-300">{response}</pre>
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
