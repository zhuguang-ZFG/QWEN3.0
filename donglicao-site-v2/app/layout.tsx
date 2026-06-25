import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LiMa 量子星云系统",
  description:
    "LiMa 量子星云系统是 AI 量子化设备调度平台，以量子路由、多模态坍缩与设备纠缠协同，连接 170+ AI 后端，驱动 AI 绘图机、写字机与 2D 数字人完成真实创作。",
  openGraph: {
    title: "LiMa 量子星云系统",
    description: "把自然语言坍缩为真实创作",
    url: "https://donglicao.com",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#07070f] text-slate-200">
        {children}
      </body>
    </html>
  );
}
