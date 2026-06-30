import Link from "next/link";
import OptimizedImage from "./OptimizedImage";

export default function Hero() {
  return (
    <section className="relative overflow-hidden px-6 pt-32 pb-20 md:pt-48 md:pb-32">
      <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2">
        <div className="space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wider text-cyan-400">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
            Quantum AI Nebula
          </div>
          <h1 className="text-4xl font-bold leading-tight tracking-tight text-slate-50 md:text-6xl">
            把自然语言
            <br />
            <span className="text-cyan-400">坍缩为真实创作</span>
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-slate-400">
            LiMa 量子星云系统连接 170+ AI 后端与智能设备。以量子路由、多模态坍缩与设备纠缠协同，一句话驱动绘画、书写、对话，让创意走出屏幕。
          </p>
          <div className="flex flex-wrap gap-4">
            <a
              href="https://app.donglicao.com"
              target="_blank"
              rel="noopener"
              className="rounded-full bg-cyan-500 px-6 py-3 font-semibold text-white hover:bg-cyan-400"
            >
              在线体验
            </a>
            <Link
              href="/developer/playground/"
              className="rounded-full border border-white/10 px-6 py-3 font-semibold text-slate-200 hover:border-cyan-500/50 hover:text-cyan-400"
            >
              查看 API
            </Link>
          </div>
          <div className="flex flex-wrap gap-3">
            {["量子路由", "多模态坍缩", "设备纠缠协同"].map((tag) => (
              <span
                key={tag}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-slate-300"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div className="relative">
          <div className="relative aspect-[4/3] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 shadow-2xl shadow-cyan-500/10">
            <OptimizedImage
              src="/assets/hero.webp"
              alt="LiMa 量子星云网络可视化"
              fill
              priority
              className="object-cover"
              sizes="(max-width: 1024px) 100vw, 50vw"
            />
          </div>
          <svg
            className="pointer-events-none absolute -inset-8 -z-10 opacity-60"
            viewBox="0 0 400 400"
            fill="none"
          >
            <circle cx="200" cy="200" r="185" stroke="rgba(6,182,212,0.22)" strokeWidth="1" strokeDasharray="14 14" />
            <circle cx="200" cy="200" r="152" stroke="rgba(139,92,246,0.18)" strokeWidth="1" strokeDasharray="10 10" />
            <circle cx="200" cy="200" r="120" stroke="rgba(6,182,212,0.12)" strokeWidth="1" strokeDasharray="6 10" />
          </svg>
        </div>
      </div>
    </section>
  );
}
