import Link from "next/link";

const links = [
  { label: "首页", href: "/" },
  { label: "AI 绘图机", href: "/product-draw/" },
  { label: "AI 写字机", href: "/product-write/" },
  { label: "2D 数字人", href: "/product-human/" },
  { label: "定价", href: "/pricing/" },
  { label: "控制台", href: "https://chat.donglicao.com", external: true },
];

export default function Footer() {
  return (
    <footer className="border-t border-white/5 px-6 py-12">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 md:flex-row">
        <div className="flex items-center gap-2 text-cyan-400">
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2l2.4 7.2h7.6l-6 4.8 2.4 7.2-6-4.8-6 4.8 2.4-7.2-6-4.8h7.6z" />
          </svg>
          <span className="font-semibold text-slate-100">LiMa 量子星云</span>
        </div>
        <nav className="flex flex-wrap justify-center gap-6 text-sm text-slate-400">
          {links.map((l) =>
            l.external ? (
              <a key={l.label} href={l.href} target="_blank" rel="noopener" className="hover:text-cyan-400">
                {l.label}
              </a>
            ) : (
              <Link key={l.label} href={l.href} className="hover:text-cyan-400">
                {l.label}
              </Link>
            )
          )}
        </nav>
        <p className="text-xs text-slate-500">© 2026 深圳市动力巢科技有限公司</p>
      </div>
    </footer>
  );
}
