import type { Metadata } from "next";
import Link from "next/link";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";

export const metadata: Metadata = {
  title: "定价 - LiMa 量子星云系统",
  description: "LiMa 量子星云系统定价方案：从免费版到企业版，选择适合你的 AI 对话、设备接入与 API 配额。",
  alternates: {
    canonical: "https://donglicao.com/pricing/",
    languages: {
      "zh-CN": "https://donglicao.com/pricing/",
      "en-US": "https://donglicao.com/en/pricing/",
      "x-default": "https://donglicao.com/pricing/",
    },
  },
};

const plans = [
  {
    name: "免费版",
    desc: "适合个人尝鲜与轻度创作",
    price: "¥0",
    featured: false,
    features: [
      { text: "每日 50 次 AI 对话", included: true },
      { text: "基础模型（GPT-3.5 级别）", included: true },
      { text: "1 台设备接入", included: true },
      { text: "社区支持", included: true },
      { text: "SVG 生成", included: false },
      { text: "API Key", included: false },
    ],
    cta: "免费开始",
    href: "https://chat.donglicao.com/register",
    primary: false,
  },
  {
    name: "创作者版",
    desc: "适合独立创作者与小工作室",
    price: "¥49",
    featured: false,
    features: [
      { text: "每日 500 次 AI 对话", included: true },
      { text: "高级模型与量子路由", included: true },
      { text: "3 台设备接入", included: true },
      { text: "SVG 生成", included: true },
      { text: "1 个 API Key", included: true },
      { text: "邮件支持", included: true },
    ],
    cta: "立即订阅",
    href: "https://chat.donglicao.com/register",
    primary: true,
  },
  {
    name: "团队版",
    desc: "适合小型团队与教室场景",
    price: "¥199",
    featured: true,
    features: [
      { text: "无限 AI 对话", included: true },
      { text: "全模型池与优先路由", included: true },
      { text: "10 台设备接入", included: true },
      { text: "SVG 生成", included: true },
      { text: "5 个 API Key", included: true },
      { text: "专属客服", included: true },
    ],
    cta: "立即订阅",
    href: "https://chat.donglicao.com/register",
    primary: true,
  },
  {
    name: "企业版",
    desc: "适合规模化部署与定制集成",
    price: "联系销售",
    featured: false,
    features: [
      { text: "不限 AI 对话", included: true },
      { text: "私有模型路由与审计", included: true },
      { text: "不限设备接入", included: true },
      { text: "SVG 生成", included: true },
      { text: "不限 API Key", included: true },
      { text: "SLA + 定制方案", included: true },
    ],
    cta: "联系销售",
    href: "mailto:sales@donglicao.com",
    primary: false,
  },
];

const rows = [
  ["月费", "¥0", "¥49", "¥199", "联系销售"],
  ["AI 对话", "50 / 天", "500 / 天", "无限", "不限"],
  ["设备接入", "1 台", "3 台", "10 台", "不限"],
  ["SVG 生成", "—", "✓", "✓", "✓"],
  ["API Key", "—", "1 个", "5 个", "不限"],
  ["支持方式", "社区", "邮件", "专属客服", "SLA + 定制"],
];

const faqs = [
  {
    q: "免费版每天有 50 次对话，用完后会怎样？",
    a: "当日额度耗尽后，你可以等待次日重置，或随时升级到创作者版/团队版以解锁更高配额。额度重置时间为北京时间每日 0 点。",
  },
  {
    q: "创作者版与团队版的模型质量有区别吗？",
    a: "所有付费档位均可访问 LiMa 量子路由全模型池。团队版与企业版享有更高的并发优先级与故障降级保障，适合多人协作或生产环境。",
  },
  {
    q: "可以随时降级或取消订阅吗？",
    a: "可以。你可以在控制台随时更改档位，变更将在当前计费周期结束后生效。取消订阅后，账户将自动回到免费版。",
  },
  {
    q: "企业版包含哪些定制服务？",
    a: "企业版提供专属 SLA、私有模型路由、审计日志、不限设备与 API Key、私有化部署咨询及优先技术支持。请发送邮件至 sales@donglicao.com 获取方案。",
  },
  {
    q: "支持哪些支付方式？",
    a: "目前支持支付宝与微信支付。企业版另外支持对公转账与合同开票，具体请联系销售团队。",
  },
];

export default function PricingPage() {
  return (
    <>
      <Navbar />
      <main id="main" className="flex-1 px-6 pt-32 pb-20">
        <div className="mx-auto max-w-7xl">
          <div className="mb-16 text-center">
            <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Pricing</div>
            <h1 className="text-3xl font-bold text-slate-50 md:text-5xl">选择适合你的创作方案</h1>
            <p className="mt-4 text-slate-400">从免费开始，随时升级</p>
            <p className="mt-2 text-sm text-slate-500">所有档位均包含 LiMa 量子星云核心路由与设备协同能力。</p>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`relative flex flex-col rounded-2xl border p-6 ${
                  plan.featured
                    ? "border-cyan-500/40 bg-cyan-500/10"
                    : "border-white/10 bg-white/[0.03]"
                }`}
              >
                {plan.featured && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-cyan-500 px-3 py-1 text-xs font-semibold text-white">
                    最受欢迎
                  </div>
                )}
                <div className="mb-4">
                  <h2 className="text-xl font-semibold text-slate-100">{plan.name}</h2>
                  <p className="text-sm text-slate-400">{plan.desc}</p>
                </div>
                <div className="mb-6 text-3xl font-bold text-slate-50">
                  {plan.price}
                  {plan.price !== "联系销售" && <span className="text-base font-normal text-slate-500">/月</span>}
                </div>
                <ul className="mb-8 flex-1 space-y-3 text-sm">
                  {plan.features.map((f) => (
                    <li key={f.text} className={`flex items-center gap-2 ${f.included ? "text-slate-300" : "text-slate-500 line-through"}`}>
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
              <h2 className="text-2xl font-bold text-slate-50">各档位功能一览</h2>
            </div>
            <div className="overflow-x-auto rounded-2xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 bg-white/5 text-slate-300">
                    <th className="px-6 py-4 font-medium">功能</th>
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
              <h2 className="text-2xl font-bold text-slate-50">定价常见问题</h2>
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
            <h2 className="text-2xl font-bold text-slate-50">还没决定？</h2>
            <p className="mt-2 text-slate-400">免费开始体验 LiMa 量子星云，随时可以升级。</p>
            <div className="mt-6 flex justify-center gap-4">
              <a
                href="https://chat.donglicao.com/register"
                target="_blank"
                rel="noopener"
                className="rounded-full bg-cyan-500 px-6 py-2.5 font-semibold text-white hover:bg-cyan-400"
              >
                免费注册
              </a>
              <Link
                href="/"
                className="rounded-full border border-white/10 px-6 py-2.5 font-semibold text-slate-200 hover:border-cyan-500/50 hover:text-cyan-400"
              >
                返回首页
              </Link>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
