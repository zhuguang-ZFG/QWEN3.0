"use client";

import { useEffect, useRef, useState } from "react";

const pipeline = [
  { step: 1, title: "意图理解", desc: "LLM 解析自然语言，识别创作类型与风格偏好" },
  { step: 2, title: "内容生成", desc: "SVG 矢量图，笔画字体渲染" },
  { step: 3, title: "路径管线", desc: "SVG 路径解析，运动轨迹生成" },
  { step: 4, title: "策略验证", desc: "协议兼容检查，安全仿真评估" },
  { step: 5, title: "设备执行", desc: "MQTT + WS，影子状态同步" },
];

const stats = [
  { value: 170, suffix: "+", label: "多后端接入" },
  { value: 30, suffix: "+", label: "多供应商接入" },
  { value: 6, suffix: "维", label: "能力评测" },
  { value: 9, suffix: "步", label: "任务状态机" },
];

function AnimatedNumber({ value, suffix }: { value: number; suffix: string }) {
  const [num, setNum] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          let start = 0;
          const duration = 1200;
          const startTime = performance.now();
          const tick = (now: number) => {
            const p = Math.min((now - startTime) / duration, 1);
            const current = Math.floor(p * value);
            if (current !== start) {
              start = current;
              setNum(current);
            }
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          observer.disconnect();
        }
      },
      { threshold: 0.5 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [value]);

  return (
    <div ref={ref} className="text-4xl font-bold text-slate-50 md:text-5xl">
      {num}
      {suffix}
    </div>
  );
}

export default function Technology() {
  return (
    <section id="technology" className="px-6 py-20">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 text-center">
          <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Technology</div>
          <h2 className="text-3xl font-bold text-slate-50 md:text-4xl">从意图到执行的量子流水线</h2>
          <p className="mt-3 text-slate-400">五步完成自然语言到真实创作的坍缩。</p>
        </div>

        <div className="grid gap-4 md:grid-cols-5">
          {pipeline.map((item) => (
            <div
              key={item.step}
              className="relative rounded-2xl border border-white/10 bg-white/[0.03] p-6 text-center"
            >
              <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500/20 text-cyan-400">
                {item.step}
              </div>
              <h3 className="text-lg font-semibold text-slate-100">{item.title}</h3>
              <p className="mt-2 text-sm text-slate-400">{item.desc}</p>
            </div>
          ))}
        </div>

        <div className="mt-16 grid grid-cols-2 gap-6 md:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              <AnimatedNumber value={s.value} suffix={s.suffix} />
              <div className="mt-1 text-sm text-slate-400">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
