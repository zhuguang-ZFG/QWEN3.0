"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const isEn = pathname?.startsWith("/en") ?? false;

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#07070f]/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2 text-cyan-400">
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2l2.4 7.2h7.6l-6 4.8 2.4 7.2-6-4.8-6 4.8 2.4-7.2-6-4.8h7.6z" />
          </svg>
          <span className="text-lg font-semibold tracking-tight text-slate-100">LiMa 量子星云</span>
        </Link>

        <button
          className="text-slate-300 md:hidden"
          aria-label={open ? "关闭菜单" : "打开菜单"}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div
          className={`${
            open ? "block" : "hidden"
          } absolute left-0 right-0 top-full border-b border-white/5 bg-[#07070f]/95 p-6 md:static md:block md:border-0 md:bg-transparent md:p-0`}
        >
          <div className="flex flex-col gap-4 text-sm text-slate-300 md:flex-row md:items-center md:gap-8">
            <Link href="/product-draw/" className="hover:text-cyan-400" onClick={() => setOpen(false)}>
              AI 绘图机
            </Link>
            <Link href="/product-write/" className="hover:text-cyan-400" onClick={() => setOpen(false)}>
              AI 写字机
            </Link>
            <Link href="/product-human/" className="hover:text-cyan-400" onClick={() => setOpen(false)}>
              2D 数字人
            </Link>
            <Link href="/pricing/" className="hover:text-cyan-400" onClick={() => setOpen(false)}>
              定价
            </Link>
            <a
              href="https://chat.donglicao.com"
              target="_blank"
              rel="noopener"
              className="rounded-full bg-cyan-500 px-4 py-2 text-center font-medium text-slate-950 hover:bg-cyan-400"
              onClick={() => setOpen(false)}
            >
              控制台
            </a>
            <Link
              href={isEn ? "/" : "/en/"}
              className="rounded-full border border-white/10 px-3 py-2 text-center text-sm text-slate-300 hover:border-white/20 hover:text-slate-100"
              onClick={() => setOpen(false)}
              aria-label={isEn ? "Switch to Chinese" : "Switch to English"}
            >
              {isEn ? "中文" : "EN"}
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
