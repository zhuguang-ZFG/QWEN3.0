import Image from "next/image";

const scenarios = [
  {
    title: "家庭创作",
    desc: "孩子说\"画一只恐龙\"，AI 绘图机立刻开始创作。亲子互动，激发想象力。",
    image: "/assets/scene-home.webp",
    tags: ["亲子互动", "创意启蒙"],
    large: true,
  },
  {
    title: "教育课堂",
    desc: "书法练习、几何绘制、诗词创作，AI 写字机让传统文化学习更有趣。",
    image: "/assets/scene-edu.webp",
    tags: ["书法练习", "几何教学"],
  },
  {
    title: "个性定制",
    desc: "手写贺卡、定制画作、个性签名，每一份礼物都独一无二。",
    image: "/assets/scene-gift.webp",
    tags: ["手写贺卡", "定制画作"],
  },
];

export default function Scenarios() {
  return (
    <section id="scenarios" className="border-y border-white/5 px-6 py-20">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold text-slate-50 md:text-4xl">适用场景</h2>
          <p className="mt-3 text-slate-400">从家庭到教室，从创意到礼物。</p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {scenarios.map((s) => (
            <div
              key={s.title}
              className={`group overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] ${
                s.large ? "md:row-span-2" : ""
              }`}
            >
              <div className={`relative ${s.large ? "aspect-[3/4]" : "aspect-video"} overflow-hidden`}>
                <Image
                  src={s.image}
                  alt={s.title}
                  fill
                  className="object-cover transition duration-500 group-hover:scale-105"
                  sizes="(max-width: 768px) 100vw, 50vw"
                />
              </div>
              <div className="p-6">
                <h3 className="text-xl font-semibold text-slate-100">{s.title}</h3>
                <p className="mt-2 text-slate-400">{s.desc}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {s.tags.map((tag) => (
                    <span key={tag} className="rounded-full bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-300">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
