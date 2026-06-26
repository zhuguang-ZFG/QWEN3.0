import type { Metadata } from "next";
import Link from "next/link";
import Navbar from "../components/Navbar";
import Partners from "../components/Partners";
import Footer from "../components/Footer";
import Reveal from "../components/Reveal";

export const metadata: Metadata = {
  title: "LiMa Quantum Nebula - AI Devices & Unified API",
  description:
    "LiMa routes 170+ AI backends into one OpenAI-compatible API and powers AI drawing, writing, and digital-human devices.",
  alternates: {
    canonical: "https://donglicao.com/en/",
    languages: {
      "en-US": "https://donglicao.com/en/",
      "zh-CN": "https://donglicao.com/",
      "x-default": "https://donglicao.com/",
    },
  },
  openGraph: {
    title: "LiMa Quantum Nebula",
    description: "One API for 170+ AI backends. Real devices. Real creation.",
    url: "https://donglicao.com/en/",
  },
};

export const dynamic = "force-static";

const enFaqs = [
  {
    q: "Which AI models does LiMa support?",
    a: "LiMa connects to 170+ backends across GPT-4o, Claude, DeepSeek, Groq, NVIDIA, OpenRouter, Cloudflare, Gemini, Mistral, SiliconFlow, Zhipu, Baidu, Tencent, Volcengine, Alibaba Cloud and more.",
  },
  {
    q: "What hardware can I connect?",
    a: "ESP32-S3 / ESP32-C3 based boards. We provide reference designs for an AI drawing machine, AI writing machine, and 2D digital human.",
  },
  {
    q: "Is my data secure?",
    a: "LiMa uses TLS transport, device remote attestation, signed OTA updates, A/B rollback, and access whitelists for end-to-end security.",
  },
  {
    q: "How do I deploy LiMa?",
    a: "One-command Docker, VPS, or local development. Production uses nginx + uvicorn with automated deployment scripts.",
  },
  {
    q: "How is billing calculated?",
    a: "Usage is metered by tokens and requests. The console shows 30-day statistics. The free tier includes 50 chats per day.",
  },
  {
    q: "Do you support private deployment?",
    a: "Yes. Enterprise plans include on-premises deployment, SLA, custom hardware adaptation, and dedicated support.",
  },
];

export default function HomeEn() {
  return (
    <>
      <Navbar />
      <main id="main" lang="en" className="flex-1">
        {/* Hero */}
        <section className="relative flex min-h-[90vh] items-center justify-center px-6 pt-20">
          <div className="mx-auto max-w-4xl text-center">
            <div className="mb-4 inline-flex items-center rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-300">
              One API · 170+ Backends · Real Devices
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-slate-50 sm:text-6xl">
              Collapse language into{" "}
              <span className="text-cyan-400">
                real creation
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400">
              LiMa is a quantum-routed AI cloud for smart hardware. Talk, draw, write, and animate through a single
              OpenAI-compatible endpoint.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <a
                href="https://chat.donglicao.com"
                target="_blank"
                rel="noopener"
                className="rounded-lg bg-cyan-500 px-6 py-3 font-semibold text-white transition hover:bg-cyan-400"
              >
                Try Console
              </a>
              <a
                href="https://docs.donglicao.com"
                target="_blank"
                rel="noopener"
                className="rounded-lg border border-white/10 bg-white/5 px-6 py-3 font-semibold text-slate-100 transition hover:bg-white/10"
              >
                Read Docs
              </a>
            </div>
          </div>
        </section>

        {/* Products */}
        <Reveal>
          <section className="px-6 py-20">
            <div className="mx-auto max-w-6xl">
              <div className="mb-3 text-center text-xs font-medium uppercase tracking-wider text-cyan-400">Products</div>
              <h2 className="text-center text-3xl font-bold text-slate-50">From prompt to physical output</h2>
              <p className="mx-auto mt-2 max-w-2xl text-center text-slate-400">
                LiMa turns words into motion, ink, and pixels on real devices.
              </p>

              <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {[
                  {
                    title: "AI Drawing Machine",
                    desc: "Generate SVG line art from prompts and watch the plotter draw it on paper.",
                    href: "/product-draw/",
                    color: "text-cyan-400",
                  },
                  {
                    title: "AI Writing Machine",
                    desc: "Handwritten notes, calligraphy, and batch documents produced by a pen robot.",
                    href: "/product-write/",
                    color: "text-violet-400",
                  },
                  {
                    title: "2D Digital Human",
                    desc: "Live2D avatar driven by LLM dialogue with voice and expression.",
                    href: "/product-human/",
                    color: "text-pink-400",
                  },
                ].map((p) => (
                  <Link
                    key={p.title}
                    href={p.href}
                    className="group rounded-2xl border border-white/10 bg-white/[0.03] p-6 transition hover:border-white/15 hover:bg-white/[0.05]"
                  >
                    <h3 className={`text-xl font-semibold ${p.color}`}>{p.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-slate-400">{p.desc}</p>
                    <span className="mt-4 inline-block text-sm font-medium text-slate-200 group-hover:text-cyan-300">
                      Learn more →
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          </section>
        </Reveal>

        {/* Partners */}
        <Reveal>
          <Partners />
        </Reveal>

        {/* FAQ */}
        <Reveal>
          <section className="px-6 py-20">
            <div className="mx-auto max-w-3xl">
              <div className="mb-3 text-center text-xs font-medium uppercase tracking-wider text-cyan-400">FAQ</div>
              <h2 className="text-center text-3xl font-bold text-slate-50">Common questions</h2>
              <div className="mt-10 space-y-4">
                {enFaqs.map((item, i) => (
                  <details
                    key={i}
                    className="group rounded-xl border border-white/10 bg-white/[0.03] open:bg-white/[0.05]"
                  >
                    <summary className="cursor-pointer list-none px-5 py-4 font-medium text-slate-100 outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50">
                      <span className="flex items-center justify-between">
                        {item.q}
                        <span className="text-cyan-400 transition group-open:rotate-45">+</span>
                      </span>
                    </summary>
                    <p className="px-5 pb-4 text-sm leading-relaxed text-slate-400">{item.a}</p>
                  </details>
                ))}
              </div>
            </div>
          </section>
        </Reveal>

        {/* CTA */}
        <section className="px-6 py-20">
          <div className="mx-auto max-w-4xl rounded-2xl border border-white/10 bg-gradient-to-br from-cyan-900/20 to-violet-900/20 p-10 text-center">
            <h2 className="text-2xl font-bold text-slate-50">Start building with LiMa today</h2>
            <p className="mt-2 text-slate-400">Free tier available. Upgrade when you scale.</p>
            <div className="mt-6 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/pricing/"
                className="rounded-lg bg-cyan-500 px-6 py-3 font-semibold text-white transition hover:bg-cyan-400"
              >
                View Pricing
              </Link>
              <Link
                href="/developer/playground/"
                className="rounded-lg border border-white/10 bg-white/5 px-6 py-3 font-semibold text-slate-100 transition hover:bg-white/10"
              >
                API Playground
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
