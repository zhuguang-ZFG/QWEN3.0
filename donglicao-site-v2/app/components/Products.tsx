import Link from "next/link";
import OptimizedImage from "./OptimizedImage";

const products = [
  {
    id: "draw",
    title: "AI 绘图机",
    desc: "自然语言生成 SVG，路径管线自动转换，一笔绘制任意图案。",
    image: "/assets/product-draw.webp",
    tags: ["SVG 生成", "路径管线", "G-code"],
    href: "/product-draw/",
    large: true,
  },
  {
    id: "write",
    title: "AI 写字机",
    desc: "笔画字体渲染、运动路径仿真，双 ESP32 协同精准书写。",
    image: "/assets/product-write.webp",
    tags: ["笔画字体", "双芯协作"],
    href: "/product-write/",
  },
  {
    id: "human",
    title: "2D 数字人",
    desc: "Live2D 实时语音交互，一句话唤醒、对话、表情同步。",
    image: "/assets/product-human.webp",
    tags: ["Live2D", "语音对话"],
    href: "/product-human/",
  },
];

const features = [
  { title: "量子星云路由", desc: "170+ 后端节点动态调度，为每个请求坍缩至最优模型。" },
  { title: "策略验证", desc: "协议兼容检查与安全仿真，确保设备动作可执行。" },
  { title: "影子状态", desc: "MQTT + WebSocket 双通道，断网自动恢复。" },
];

export default function Products() {
  return (
    <section id="products" className="px-6 py-20">
      <div className="mx-auto max-w-7xl">
        <div className="mb-14 text-center">
          <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Products</div>
          <h2 className="text-3xl font-bold text-slate-50 md:text-4xl">一个中枢，多种创作</h2>
          <p className="mt-3 text-slate-400">从意图到执行，LiMa 统一调度 AI 能力与设备动作。</p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <Link
              key={p.id}
              href={p.href}
              className={`group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-6 transition hover:border-cyan-500/30 hover:bg-white/[0.05] ${p.large ? "md:col-span-2 lg:col-span-2" : ""}`}
            >
              {p.image && (
                <div className="relative mb-6 aspect-video overflow-hidden rounded-xl">
                  <OptimizedImage
                    src={p.image}
                    alt={p.title}
                    fill
                    className="object-cover transition duration-500 group-hover:scale-105"
                    sizes="(max-width: 768px) 100vw, 50vw"
                  />
                </div>
              )}
              <h3 className="text-xl font-semibold text-slate-100">{p.title}</h3>
              <p className="mt-2 text-slate-400">{p.desc}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {p.tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-300">
                    {tag}
                  </span>
                ))}
              </div>
            </Link>
          ))}

          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 transition hover:border-cyan-500/30 hover:bg-white/[0.05]"
            >
              <h3 className="text-lg font-semibold text-slate-100">{f.title}</h3>
              <p className="mt-2 text-sm text-slate-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
