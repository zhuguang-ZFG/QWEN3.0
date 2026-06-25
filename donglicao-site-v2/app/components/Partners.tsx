import Image from "next/image";

const logos = [
  { file: "gpt4o.svg", name: "GPT-4o" },
  { file: "claude.svg", name: "Claude" },
  { file: "deepseek.svg", name: "DeepSeek" },
  { file: "groq.svg", name: "Groq" },
  { file: "nvidia.svg", name: "NVIDIA" },
  { file: "openrouter.svg", name: "OpenRouter" },
  { file: "cloudflare.svg", name: "Cloudflare" },
  { file: "google-ai.svg", name: "Google AI" },
  { file: "gemini.svg", name: "Gemini" },
  { file: "mistral.svg", name: "Mistral" },
  { file: "siliconflow.svg", name: "SiliconFlow" },
  { file: "zhipu.svg", name: "Zhipu" },
  { file: "baidu.svg", name: "Baidu" },
  { file: "tencent.svg", name: "Tencent" },
  { file: "volcengine.svg", name: "Volcengine" },
  { file: "aliyun.svg", name: "Aliyun" },
  { file: "llama.svg", name: "Llama" },
  { file: "longcat.svg", name: "LongCat" },
  { file: "cohere.svg", name: "Cohere" },
  { file: "replicate.svg", name: "Replicate" },
  { file: "together.svg", name: "Together AI" },
];

export default function Partners() {
  return (
    <section id="partners" className="border-y border-white/5 px-6 py-16">
      <div className="mx-auto max-w-7xl text-center">
        <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Partners</div>
        <h2 className="text-2xl font-bold text-slate-50 md:text-3xl">接入 170+ AI 后端</h2>
        <p className="mt-2 text-slate-400">与全球领先模型与平台无缝协作。</p>

        <div className="mt-10 grid grid-cols-3 gap-4 sm:grid-cols-4 md:grid-cols-6">
          {logos.map(({ file, name }) => (
            <div
              key={file}
              className="group flex items-center justify-center rounded-xl bg-white/5 p-4 transition-all duration-300 hover:bg-white/10 hover:shadow-lg hover:shadow-cyan-900/10"
              title={name}
            >
              <Image
                src={`/assets/logos/${file}`}
                alt={name}
                width={120}
                height={36}
                loading="lazy"
                decoding="async"
                className="h-8 w-auto object-contain opacity-60 grayscale transition-all duration-300 group-hover:scale-105 group-hover:opacity-100 group-hover:grayscale-0"
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
