const testimonials = [
  {
    quote: "AI 绘图机让我们的线下活动有了互动焦点。观众一句话就能出图，现场氛围完全不一样了。",
    name: "林晓",
    role: "创意工作室主理人",
    color: "#67e8f9",
  },
  {
    quote: "写字机让书法课变得生动，学生注意力明显提高。AI 生成的笔画演示是传统教学很好的补充。",
    name: "王志强",
    role: "小学书法教师",
    color: "#fbbf24",
  },
  {
    quote: "定制手写贺卡成了我们店最受欢迎的 SKU。客户愿意为独一无二的祝福多等一天。",
    name: "陈雨桐",
    role: "手作礼物店主",
    color: "#fb7185",
  },
];

export default function Testimonials() {
  return (
    <section id="testimonials" className="px-6 py-20">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 text-center">
          <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Testimonials</div>
          <h2 className="text-3xl font-bold text-slate-50 md:text-4xl">用户怎么说</h2>
          <p className="mt-3 text-slate-400">从创作者到教育者，LiMa 正在让真实创作变得简单。</p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {testimonials.map((t) => (
            <div
              key={t.name}
              className="flex flex-col justify-between rounded-2xl border border-white/10 bg-white/[0.03] p-6"
            >
              <p className="text-lg italic text-slate-300">&ldquo;{t.quote}&rdquo;</p>
              <div className="mt-6 flex items-center gap-3">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold"
                  style={{ backgroundColor: `${t.color}20`, color: t.color }}
                >
                  {t.name[0]}
                </div>
                <div>
                  <div className="font-medium text-slate-100">{t.name}</div>
                  <div className="text-sm text-slate-500">{t.role}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
