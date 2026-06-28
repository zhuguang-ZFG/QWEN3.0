import Image from "next/image";
import Link from "next/link";

const footerLinks = [
  {
    title: "产品",
    links: [
      { label: "首页", href: "/" },
      { label: "AI 绘图机", href: "/product-draw/" },
      { label: "AI 写字机", href: "/product-write/" },
      { label: "2D 数字人", href: "/product-human/" },
      { label: "定价", href: "/pricing/" },
    ],
  },
  {
    title: "开发者",
    links: [
      { label: "API 文档", href: "https://docs.donglicao.com", external: true },
      { label: "API Playground", href: "/developer/playground/" },
      { label: "GitHub", href: "https://github.com/zhuguang-ZFG/QWEN3.0", external: true },
      { label: "Gitee", href: "https://gitee.com/zhuguang-cn/QWEN3.0", external: true },
    ],
  },
  {
    title: "账户",
    links: [
      { label: "登录", href: "/login/" },
      { label: "注册", href: "/register/" },
    ],
  },
  {
    title: "法律",
    links: [
      { label: "隐私政策", href: "/privacy/" },
      { label: "用户协议", href: "/terms/" },
    ],
  },
  {
    title: "公司",
    links: [
      { label: "关于我们", href: "/#hero" },
      { label: "博客", href: "/blog/" },
      { label: "联系销售", href: "mailto:sales@donglicao.com" },
    ],
  },
];

const socials = [
  {
    label: "微信公众号",
    href: "#",
    qr: "/assets/wechat-qr.png",
    svg: (
      <path d="M8.5 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm4-1a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm-7.5-2C3.6 6.5 6.9 4 11 4c3.5 0 6.5 1.9 6.5 5 0 2.6-2.1 4.5-5 4.9l-1.5 1.5.5-1.8C8.2 13.2 5 12 5 10zm13.5 3c0-2.4-2.4-4.1-5.3-4.5.2.4.3.9.3 1.5 0 3.3-3.3 5.5-7 5.5-.6 0-1.2-.1-1.7-.2 1.1 2 3.8 3.2 6.7 3.2.6 0 1.1 0 1.7-.1l1.4 1.4-.5-1.6c2.4-.8 3.4-2.4 3.4-4.3z" />
    ),
  },
  {
    label: "微博",
    href: "#",
    svg: (
      <path d="M10.8 3.5c4.5 0 8.2 3 8.2 6.7 0 3.8-3.7 6.8-8.2 6.8-1 0-2-.1-2.9-.4L5.5 18l.6-2.4C4.5 14.2 3.5 12.6 3.5 10.8c0-4.2 3.3-7.3 7.3-7.3zm4.5 4.6c.4 0 .7-.3.7-.7s-.3-.7-.7-.7-.7.3-.7.7.3.7.7.7zm-3.4-.9c.3 0 .6-.3.6-.6s-.3-.6-.6-.6-.6.3-.6.6.3.6.6.6zm1.5 3.5c-.4-1.4-2-2.1-3.5-1.7-1.5.4-2.4 1.8-2 3.1.4 1.3 1.9 2 3.4 1.6 1.5-.3 2.5-1.6 2.1-3z" />
    ),
  },
  {
    label: "哔哩哔哩",
    href: "#",
    svg: <path d="M2 6h20l-2 13H4L2 6zm4 5h5v5H6v-5zm7 0h5v5h-5v-5z" />,
  },
  {
    label: "抖音",
    href: "#",
    svg: <path d="M16 4v9.5c0 2.5-2 4.5-4.5 4.5S7 16 7 13.5 9 9 11.5 9c.6 0 1.2.1 1.7.4V4h3z" />,
  },
  {
    label: "GitHub",
    href: "https://github.com/zhuguang-ZFG/QWEN3.0",
    external: true,
    svg: (
      <path d="M12 2C6.48 2 2 6.48 2 12c0 4.42 2.87 8.17 6.84 9.49.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.89 1.52 2.34 1.08 2.91.83.09-.65.35-1.08.63-1.33-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02A9.56 9.56 0 0 1 12 6.8c.85 0 1.71.11 2.51.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 22 12c0-5.52-4.48-10-10-10z" />
    ),
  },
];

export default function Footer() {
  return (
    <footer className="border-t border-white/5 px-6 py-14">
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-12 md:grid-cols-2 lg:grid-cols-6">
          <div className="lg:col-span-2">
            <Link href="/" className="flex items-center gap-2 text-cyan-400">
              <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l2.4 7.2h7.6l-6 4.8 2.4 7.2-6-4.8-6 4.8 2.4-7.2-6-4.8h7.6z" />
              </svg>
              <span className="text-lg font-semibold text-slate-100">LiMa 量子星云</span>
            </Link>
            <p className="mt-3 max-w-xs text-sm text-slate-500">
              量子化的 AI 智能设备星云系统，把自然语言坍缩为真实创作。
            </p>
            <div className="mt-4 flex items-center gap-3">
              {socials.map((s) =>
                s.qr ? (
                  <div key={s.label} className="group relative">
                    <a
                      href={s.href}
                      aria-label={s.label}
                      className="flex h-9 w-9 items-center justify-center rounded-full bg-white/5 text-slate-400 transition hover:bg-white/10 hover:text-cyan-400"
                    >
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                        {s.svg}
                      </svg>
                    </a>
                    <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 w-32 -translate-x-1/2 rounded-lg border border-white/10 bg-[#0d1117] p-2 opacity-0 transition group-hover:opacity-100">
                      <Image src={s.qr} alt={s.label} width={112} height={112} className="rounded" />
                      <span className="mt-1 block text-center text-xs text-slate-400">{s.label}</span>
                    </div>
                  </div>
                ) : (
                  <a
                    key={s.label}
                    href={s.href}
                    target={s.external ? "_blank" : undefined}
                    rel={s.external ? "noopener" : undefined}
                    aria-label={s.label}
                    className="flex h-9 w-9 items-center justify-center rounded-full bg-white/5 text-slate-400 transition hover:bg-white/10 hover:text-cyan-400"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                      {s.svg}
                    </svg>
                  </a>
                )
              )}
            </div>
          </div>

          {footerLinks.map((col) => (
            <div key={col.title}>
              <h4 className="mb-4 text-sm font-semibold text-slate-100">{col.title}</h4>
              <ul className="space-y-2 text-sm text-slate-400">
                {col.links.map((l) => (
                  <li key={l.label}>
                    {l.href.startsWith("http") || l.href.startsWith("mailto") ? (
                      <a
                        href={l.href}
                        target={l.href.startsWith("http") ? "_blank" : undefined}
                        rel={l.href.startsWith("http") ? "noopener" : undefined}
                        className="hover:text-cyan-400"
                      >
                        {l.label}
                      </a>
                    ) : (
                      <Link href={l.href} className="hover:text-cyan-400">
                        {l.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-2 border-t border-white/5 pt-8 text-xs text-slate-600 md:flex-row">
          <span>深圳市动力巢科技有限公司 - Copyright 2024-2026 DongLiCao Technology. All rights reserved.</span>
          <span>{process.env.NEXT_PUBLIC_ICP_NUMBER || "京ICP备XXXXXXXX号-1"}</span>
        </div>
      </div>
    </footer>
  );
}
