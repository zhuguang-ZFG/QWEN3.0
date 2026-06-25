import Image from "next/image";
import Navbar from "./Navbar";
import Footer from "./Footer";

export interface Feature {
  icon: React.ReactNode;
  title: string;
  desc: string;
}

export interface Scenario {
  icon: React.ReactNode;
  title: string;
  desc: string;
}

export interface FAQ {
  q: string;
  a: string;
}

export interface ProductPageProps {
  eyebrow: string;
  title: string;
  highlight: string;
  description: string;
  heroImage: string;
  accent: string;
  features: Feature[];
  specs: [string, string][];
  scenarios?: Scenario[];
  faqs?: FAQ[];
}

export default function ProductPage({
  eyebrow,
  title,
  highlight,
  description,
  heroImage,
  accent,
  features,
  specs,
  scenarios,
  faqs,
}: ProductPageProps) {
  return (
    <>
      <Navbar />
      <main className="flex-1 px-6 pt-32 pb-20">
        <section className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2">
          <div className="space-y-6">
            <div
              className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium uppercase tracking-wider"
              style={{ backgroundColor: `${accent}20`, color: accent }}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accent }} />
              {eyebrow}
            </div>
            <h1 className="text-4xl font-bold leading-tight text-slate-50 md:text-5xl">
              {title}
              <br />
              <span style={{ color: accent }}>{highlight}</span>
            </h1>
            <p className="text-lg leading-relaxed text-slate-400">{description}</p>
            <div className="flex flex-wrap gap-4">
              <a
                href="https://chat.donglicao.com"
                target="_blank"
                rel="noopener"
                className="rounded-full px-6 py-3 font-semibold text-slate-950"
                style={{ backgroundColor: accent }}
              >
                在线体验
              </a>
              <a
                href="https://docs.donglicao.com"
                target="_blank"
                rel="noopener"
                className="rounded-full border border-white/10 px-6 py-3 font-semibold text-slate-200 hover:border-cyan-500/50 hover:text-cyan-400"
              >
                查看文档
              </a>
            </div>
          </div>
          <div className="relative aspect-[4/3] overflow-hidden rounded-2xl border border-white/10">
            <Image
              src={heroImage}
              alt={title}
              fill
              className="object-cover"
              sizes="(max-width: 1024px) 100vw, 50vw"
            />
          </div>
        </section>

        <section className="mx-auto mt-24 max-w-7xl">
          <div className="mb-10 text-center">
            <h2 className="text-2xl font-bold text-slate-50 md:text-3xl">核心能力</h2>
            <p className="mt-2 text-slate-400">从输入到执行，全流程自动化。</p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {features.map((f, i) => (
              <div
                key={i}
                className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 transition hover:border-cyan-500/30 hover:bg-white/[0.05]"
              >
                <div className="mb-4" style={{ color: accent }}>
                  {f.icon}
                </div>
                <h3 className="text-lg font-semibold text-slate-100">{f.title}</h3>
                <p className="mt-2 text-sm text-slate-400">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto mt-24 max-w-4xl">
          <div className="mb-10 text-center">
            <h2 className="text-2xl font-bold text-slate-50 md:text-3xl">技术规格</h2>
            <p className="mt-2 text-slate-400">硬件与性能参数，供采购与集成参考。</p>
          </div>
          <div className="overflow-hidden rounded-2xl border border-white/10">
            <table className="w-full text-left text-sm">
              <tbody>
                {specs.map(([k, v]) => (
                  <tr key={k} className="border-b border-white/5 last:border-0">
                    <th className="w-1/3 bg-white/5 px-6 py-4 font-medium text-slate-300">{k}</th>
                    <td className="px-6 py-4 text-slate-400">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {scenarios && scenarios.length > 0 && (
          <section className="mx-auto mt-24 max-w-7xl">
            <div className="mb-10 text-center">
              <h2 className="text-2xl font-bold text-slate-50 md:text-3xl">使用场景</h2>
              <p className="mt-2 text-slate-400">已在这些场景中释放真实价值。</p>
            </div>
            <div className="grid gap-6 md:grid-cols-3">
              {scenarios.map((s, i) => (
                <div
                  key={i}
                  className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 transition hover:border-cyan-500/30 hover:bg-white/[0.05]"
                >
                  <div className="mb-4" style={{ color: accent }}>
                    {s.icon}
                  </div>
                  <h3 className="text-lg font-semibold text-slate-100">{s.title}</h3>
                  <p className="mt-2 text-sm text-slate-400">{s.desc}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {faqs && faqs.length > 0 && (
          <section className="mx-auto mt-24 max-w-3xl">
            <div className="mb-10 text-center">
              <h2 className="text-2xl font-bold text-slate-50 md:text-3xl">常见问题</h2>
            </div>
            <div className="space-y-4">
              {faqs.map((faq, i) => (
                <details key={i} className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-slate-300">
                  <summary className="cursor-pointer font-medium text-slate-100">{faq.q}</summary>
                  <p className="mt-3 text-slate-400">{faq.a}</p>
                </details>
              ))}
            </div>
          </section>
        )}
      </main>
      <Footer />
    </>
  );
}
