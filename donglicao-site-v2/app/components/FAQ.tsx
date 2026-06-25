"use client";

import { useState } from "react";

const faqs = [
  {
    q: "LiMa 支持哪些 AI 模型？",
    a: "LiMa 已接入 170+ 后端，覆盖 GPT-4o、Claude、DeepSeek、Groq、NVIDIA、OpenRouter、Cloudflare、Gemini、Mistral、SiliconFlow、智谱、百度、腾讯、火山引擎、阿里云等 30+ 供应商。",
  },
  {
    q: "设备兼容哪些开发板？",
    a: "当前主要支持 ESP32-S3、ESP32-C3 等乐鑫系列开发板，适配 u1-grbl 绘图/写字机、u8-xiaozhi 语音助手与 2D 数字人硬件。",
  },
  {
    q: "数据是否安全？",
    a: "LiMa 提供设备远程证明、OTA 签名验证、A/B 分区回滚、TLS 传输加密与访问白名单，确保端到端安全。",
  },
  {
    q: "如何部署？",
    a: "支持 Docker 一键部署、VPS 部署与本地开发模式。生产环境使用 nginx + uvicorn，并提供自动化部署脚本。",
  },
  {
    q: "支持私有化部署吗？",
    a: "企业版支持私有化部署与定制集成，可联系销售获取 SLA、专属支持与硬件适配服务。",
  },
  {
    q: "如何计费？",
    a: "按 Token 消耗与请求次数计费，控制台提供近 30 天用量统计。免费版每日 50 次对话，创作者版与团队版提供更高配额。",
  },
  {
    q: "可以退款吗？",
    a: "付费版本支持 7 天无理由退款，可通过邮件或专属客服提交退款申请。",
  },
  {
    q: "支持多种设备协同吗？",
    a: "支持。LiMa 提供多设备绑定、事件溯源、任务队列与 WebSocket 实时状态，绘图机、写字机、语音助手可协同工作。",
  },
  {
    q: "API 有速率限制吗？",
    a: "按账号档位限制。免费版与创作者版有 RPM 上限，团队版与企业版限制更宽松，详见定价页。",
  },
  {
    q: "固件如何升级？",
    a: "通过 OTA 远程升级，支持灰度发布、版本回滚与签名校验。控制台与小程序均可触发升级并查看进度。",
  },
  {
    q: "小程序支持哪些语言？",
    a: "uni-app 小程序已支持简体中文、繁体中文、英语、德语、葡萄牙语、越南语等多语言切换。",
  },
  {
    q: "如何获取技术支持？",
    a: "免费版可通过社区与文档自助解决；创作者版提供邮件支持；团队版与企业版提供专属客服与 SLA 保障。",
  },
];

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const structuredData = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.a,
      },
    })),
  };

  return (
    <section id="faq" className="px-6 py-16">
      <div className="mx-auto max-w-4xl">
        <div className="mb-3 text-center text-xs font-medium uppercase tracking-wider text-cyan-400">FAQ</div>
        <h2 className="text-center text-2xl font-bold text-slate-50 md:text-3xl">常见问题</h2>
        <p className="mt-2 text-center text-slate-400">关于 LiMa 平台、设备与计费的常见疑问。</p>

        <div className="mt-10 space-y-3">
          {faqs.map((item, index) => {
            const isOpen = openIndex === index;
            return (
              <div
                key={index}
                className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.03] transition-colors hover:border-white/15"
              >
                <button
                  type="button"
                  onClick={() => setOpenIndex(isOpen ? null : index)}
                  aria-expanded={isOpen}
                  className="flex w-full items-center justify-between px-5 py-4 text-left text-slate-100 transition-colors hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
                >
                  <span className="font-medium">{item.q}</span>
                  <span
                    aria-hidden="true"
                    className={`ml-4 text-cyan-400 transition-transform duration-300 ${isOpen ? "rotate-45" : ""}`}
                  >
                    +
                  </span>
                </button>
                <div
                  className={`overflow-hidden transition-all duration-300 ${isOpen ? "max-h-96" : "max-h-0"}`}
                >
                  <p className="px-5 pb-4 text-sm leading-relaxed text-slate-400">{item.a}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
    </section>
  );
}
