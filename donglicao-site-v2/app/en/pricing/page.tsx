import type { Metadata } from "next";
import Link from "next/link";
import Navbar from "../../components/Navbar";
import Footer from "../../components/Footer";

export const metadata: Metadata = {
  title: "Pricing - LiMa Quantum Nebula",
  description:
    "LiMa pricing plans: from free tier to enterprise, choose the right AI chat, device access and API quota.",
  alternates: {
    canonical: "https://donglicao.com/en/pricing/",
    languages: {
      "en-US": "https://donglicao.com/en/pricing/",
      "zh-CN": "https://donglicao.com/pricing/",
      "x-default": "https://donglicao.com/pricing/",
    },
  },
};

export const dynamic = "force-static";

const plans = [
  {
    name: "Free",
    desc: "For personal experiments and light creation",
    price: "$0",
    featured: false,
    features: [
      { text: "50 AI chats per day", included: true },
      { text: "Basic models (GPT-3.5 class)", included: true },
      { text: "1 connected device", included: true },
      { text: "Community support", included: true },
      { text: "SVG generation", included: false },
      { text: "API Key", included: false },
    ],
    cta: "Start free",
    href: "https://chat.donglicao.com/register",
    primary: false,
  },
  {
    name: "Creator",
    desc: "For indie creators and small studios",
    price: "$7",
    featured: false,
    features: [
      { text: "500 AI chats per day", included: true },
      { text: "Advanced models & quantum routing", included: true },
      { text: "3 connected devices", included: true },
      { text: "SVG generation", included: true },
      { text: "1 API Key", included: true },
      { text: "Email support", included: true },
    ],
    cta: "Subscribe",
    href: "https://chat.donglicao.com/register",
    primary: true,
  },
  {
    name: "Team",
    desc: "For small teams and classrooms",
    price: "$29",
    featured: true,
    features: [
      { text: "Unlimited AI chats", included: true },
      { text: "Full model pool & priority routing", included: true },
      { text: "10 connected devices", included: true },
      { text: "SVG generation", included: true },
      { text: "5 API Keys", included: true },
      { text: "Dedicated support", included: true },
    ],
    cta: "Subscribe",
    href: "https://chat.donglicao.com/register",
    primary: true,
  },
  {
    name: "Enterprise",
    desc: "For scaled deployment and custom integration",
    price: "Contact sales",
    featured: false,
    features: [
      { text: "Unlimited AI chats", included: true },
      { text: "Private model routing & audit logs", included: true },
      { text: "Unlimited connected devices", included: true },
      { text: "SVG generation", included: true },
      { text: "Unlimited API Keys", included: true },
      { text: "SLA + custom solutions", included: true },
    ],
    cta: "Contact sales",
    href: "mailto:sales@donglicao.com",
    primary: false,
  },
];

const rows = [
  ["Monthly fee", "$0", "$7", "$29", "Contact sales"],
  ["AI chats", "50 / day", "500 / day", "Unlimited", "Unlimited"],
  ["Devices", "1", "3", "10", "Unlimited"],
  ["SVG generation", "—", "✓", "✓", "✓"],
  ["API Keys", "—", "1", "5", "Unlimited"],
  ["Support", "Community", "Email", "Dedicated", "SLA + custom"],
];

const faqs = [
  {
    q: "What happens when the free daily quota runs out?",
    a: "Your quota resets at midnight UTC. You can upgrade to Creator or Team anytime for more daily chats and features.",
  },
  {
    q: "Is there a difference in model quality between plans?",
    a: "All paid plans can access LiMa's full quantum-routed model pool. Team and Enterprise get higher concurrency priority and fallback guarantees.",
  },
  {
    q: "Can I downgrade or cancel at any time?",
    a: "Yes. You can change plans from the console at any time. Changes take effect at the end of the current billing cycle.",
  },
  {
    q: "What is included in Enterprise?",
    a: "Enterprise includes a dedicated SLA, private model routing, audit logs, unlimited devices and API keys, on-premises consulting, and priority technical support.",
  },
  {
    q: "What payment methods are supported?",
    a: "We currently support Alipay and WeChat Pay. Enterprise customers can also pay by bank transfer with contract and invoice.",
  },
];

export default function PricingEnPage() {
  return (
    <>
      <Navbar />
      <main id="main" lang="en" className="flex-1 px-6 pt-32 pb-20">
        <div className="mx-auto max-w-7xl">
          <div className="mb-16 text-center">
            <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Pricing</div>
            <h1 className="text-3xl font-bold text-slate-50 md:text-5xl">Choose your plan</h1>
            <p className="mt-4 text-slate-400">Start free and upgrade as you grow.</p>
            <p className="mt-2 text-sm text-slate-500">
              All plans include LiMa quantum routing and device collaboration.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`relative flex flex-col rounded-2xl border p-6 ${
                  plan.featured ? "border-cyan-500/40 bg-cyan-500/10" : "border-white/10 bg-white/[0.03]"
                }`}
              >
                {plan.featured && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-cyan-500 px-3 py-1 text-xs font-semibold text-white">
                    Most popular
                  </div>
                )}
                <div className="mb-4">
                  <h2 className="text-xl font-semibold text-slate-100">{plan.name}</h2>
                  <p className="text-sm text-slate-400">{plan.desc}</p>
                </div>
                <div className="mb-6 text-3xl font-bold text-slate-50">
                  {plan.price}
                  {plan.price !== "Contact sales" && (
                    <span className="text-base font-normal text-slate-500">/mo</span>
                  )}
                </div>
                <ul className="mb-8 flex-1 space-y-3 text-sm">
                  {plan.features.map((f) => (
                    <li
                      key={f.text}
                      className={`flex items-center gap-2 ${f.included ? "text-slate-300" : "text-slate-500 line-through"}`}
                    >
                      <span className={f.included ? "text-cyan-400" : "text-slate-600"}>✓</span>
                      {f.text}
                    </li>
                  ))}
                </ul>
                <a
                  href={plan.href}
                  target={plan.href.startsWith("http") ? "_blank" : undefined}
                  rel={plan.href.startsWith("http") ? "noopener" : undefined}
                  className={`block rounded-full py-2.5 text-center font-semibold ${
                    plan.primary
                      ? "bg-cyan-500 text-white hover:bg-cyan-400"
                      : "border border-white/10 text-slate-200 hover:border-cyan-500/50 hover:text-cyan-400"
                  }`}
                >
                  {plan.cta}
                </a>
              </div>
            ))}
          </div>

          <div className="mt-20">
            <div className="mb-8 text-center">
              <h2 className="text-2xl font-bold text-slate-50">Compare features</h2>
            </div>
            <div className="overflow-x-auto rounded-2xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 bg-white/5 text-slate-300">
                    <th className="px-6 py-4 font-medium">Feature</th>
                    {plans.map((p) => (
                      <th key={p.name} className="px-6 py-4 font-medium">
                        {p.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row[0]} className="border-b border-white/5 text-slate-400 last:border-0">
                      {row.map((cell, i) => (
                        <td key={i} className="px-6 py-4">
                          {cell === "✓" ? <span className="text-cyan-400">✓</span> : cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-20 max-w-3xl">
            <div className="mb-8 text-center">
              <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">FAQ</div>
              <h2 className="text-2xl font-bold text-slate-50">Pricing FAQ</h2>
            </div>
            <div className="space-y-4">
              {faqs.map((faq) => (
                <details
                  key={faq.q}
                  className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-slate-300"
                >
                  <summary className="cursor-pointer font-medium text-slate-100">{faq.q}</summary>
                  <p className="mt-3 text-slate-400">{faq.a}</p>
                </details>
              ))}
            </div>
          </div>

          <div className="mt-20 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-10 text-center">
            <h2 className="text-2xl font-bold text-slate-50">Still deciding?</h2>
            <p className="mt-2 text-slate-400">Start free and upgrade whenever you are ready.</p>
            <div className="mt-6 flex justify-center gap-4">
              <a
                href="https://chat.donglicao.com/register"
                target="_blank"
                rel="noopener"
                className="rounded-full bg-cyan-500 px-6 py-2.5 font-semibold text-white hover:bg-cyan-400"
              >
                Sign up free
              </a>
              <Link
                href="/en/"
                className="rounded-full border border-white/10 px-6 py-2.5 font-semibold text-slate-200 hover:border-cyan-500/50 hover:text-cyan-400"
              >
                Back to home
              </Link>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
