import Image from "next/image";

const logos = [
  "gpt4o.svg",
  "claude.svg",
  "deepseek.svg",
  "groq.svg",
  "nvidia.svg",
  "openrouter.svg",
  "cloudflare.svg",
  "google-ai.svg",
  "mistral.svg",
  "siliconflow.svg",
  "zhipu.svg",
  "baidu.svg",
  "tencent.svg",
  "volcengine.svg",
  "aliyun.svg",
];

export default function Partners() {
  return (
    <section id="partners" className="border-y border-white/5 px-6 py-16">
      <div className="mx-auto max-w-7xl text-center">
        <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Partners</div>
        <h2 className="text-2xl font-bold text-slate-50 md:text-3xl">接入 170+ AI 后端</h2>
        <p className="mt-2 text-slate-400">与全球领先模型与平台无缝协作。</p>

        <div className="mt-10 grid grid-cols-3 gap-6 opacity-70 md:grid-cols-5">
          {logos.map((logo) => (
            <div key={logo} className="flex items-center justify-center rounded-xl bg-white/5 p-4">
              <Image
                src={`/assets/logos/${logo}`}
                alt={logo.replace(".svg", "")}
                width={120}
                height={36}
                loading="lazy"
                decoding="async"
                className="h-8 w-auto object-contain"
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
