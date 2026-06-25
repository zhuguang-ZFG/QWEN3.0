import type { Metadata } from "next";
import ProductPage from "../components/ProductPage";
import Icon from "../components/Icon";

export const metadata: Metadata = {
  title: "AI 绘图机 - LiMa 量子星云",
  description: "LiMa AI 绘图机：一句话将自然语言坍缩为真实笔触，支持 SVG 矢量化、多设备协同与 170+ AI 模型后端驱动。",
  alternates: {
    canonical: "https://donglicao.com/product-draw/",
    languages: {
      "zh-CN": "https://donglicao.com/product-draw/",
      "en-US": "https://donglicao.com/en/product-draw/",
      "x-default": "https://donglicao.com/product-draw/",
    },
  },
};

export default function ProductDraw() {
  return (
    <ProductPage
      eyebrow="AI Drawing Machine"
      title="AI 绘图机"
      highlight="把想象绘成现实"
      description="一句话生成矢量插画、工程草图或艺术画作，LiMa 通过量子路由选择最佳图像模型，将 SVG 路径实时下发到绘图机，让 AI 的想象力落在纸面。"
      heroImage="/assets/product-draw.webp"
      accent="#06b6d4"
      features={[
        { icon: <Icon name="route" />, title: "量子路由选模", desc: "根据风格、成本与实时健康状态，自动在 170+ 后端中挑选最优图像模型。" },
        { icon: <Icon name="image" />, title: "SVG 矢量化", desc: "输出可无限缩放的矢量路径，适配不同尺寸纸张与雕刻/切割工艺。" },
        { icon: <Icon name="grid" />, title: "多机协同", desc: "超大画面可自动分割到多台绘图机并行绘制，结果无缝拼接。" },
        { icon: <Icon name="shield" />, title: "安全仿真", desc: "落笔前先在云端仿真路径，避免越界、撞机或损坏画布。" },
      ]}
      specs={[
        ["有效绘制面积", "A3 / A4 / 自定义（最大 420mm × 300mm）"],
        ["驱动方式", "双轴步进电机 + GRBL 控制板"],
        ["通信协议", "MQTT / WebSocket / 本地串口"],
        ["支持输入", "文本 prompt、SVG、PNG 轮廓、草图参考"],
        ["云端模型", "Stable Diffusion / DALL·E / Recraft / 自定义"],
        ["协同数量", "单任务最多 16 台设备并行"],
      ]}
    />
  );
}
