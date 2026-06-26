"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";

export default function LoginPage() {
  const [baseUrl, setBaseUrl] = useState("https://chat.donglicao.com");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const saved = localStorage.getItem("lima_token");
    if (saved) {
      window.location.href = `${baseUrl}/`;
    }
  }, [baseUrl]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${baseUrl}/device/v1/app/auth/login-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.message || `登录失败（HTTP ${res.status}）`);
        return;
      }
      if (data.token) {
        localStorage.setItem("lima_token", data.token);
        window.location.href = `${baseUrl}/`;
      } else {
        setError("响应中缺少 token");
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
      <main id="main" className="flex flex-1 items-center justify-center px-6 py-32">
        <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.03] p-8">
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-bold text-slate-50">登录 LiMa</h1>
            <p className="mt-2 text-sm text-slate-400">输入邮箱和密码进入控制台</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm text-slate-300">邮箱</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-4 py-2 text-slate-200 outline-none focus:border-cyan-500"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-300">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-[#0d1117] px-4 py-2 text-slate-200 outline-none focus:border-cyan-500"
                required
              />
            </div>

            {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-cyan-500 py-2.5 font-semibold text-white hover:bg-cyan-400 disabled:opacity-60"
            >
              {loading ? "登录中..." : "登录"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-400">
            还没有账户？{" "}
            <Link href="/register/" className="text-cyan-400 hover:underline">
              立即注册
            </Link>
          </p>
        </div>
      </main>
      <Footer />
    </>
  );
}
