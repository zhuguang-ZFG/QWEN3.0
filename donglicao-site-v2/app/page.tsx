import type { Metadata } from "next";
import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import Products from "./components/Products";
import Technology from "./components/Technology";
import Scenarios from "./components/Scenarios";
import Testimonials from "./components/Testimonials";
import Developer from "./components/Developer";
import Partners from "./components/Partners";
import FAQ from "./components/FAQ";
import Footer from "./components/Footer";
import Reveal from "./components/Reveal";

export const metadata: Metadata = {
  title: "LiMa 量子星云系统",
  description:
    "LiMa 量子星云系统是 AI 量子化设备调度平台，以量子路由、多模态坍缩与设备纠缠协同，连接 170+ AI 后端，驱动 AI 绘图机、写字机与 2D 数字人完成真实创作。",
  alternates: {
    canonical: "https://www.donglicao.com/",
    languages: {
      "zh-CN": "https://www.donglicao.com/",
      "en-US": "https://www.donglicao.com/en/",
      "x-default": "https://www.donglicao.com/",
    },
  },
};

export default function Home() {
  return (
    <>
      <Navbar />
      <main id="main" className="flex-1">
        <Hero />
        <Reveal>
          <Products />
        </Reveal>
        <Reveal>
          <Technology />
        </Reveal>
        <Reveal>
          <Scenarios />
        </Reveal>
        <Reveal>
          <Testimonials />
        </Reveal>
        <Reveal>
          <Developer />
        </Reveal>
        <Reveal>
          <Partners />
        </Reveal>
        <Reveal>
          <FAQ />
        </Reveal>
      </main>
      <Footer />
    </>
  );
}
