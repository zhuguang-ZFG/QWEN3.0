import type { Metadata } from "next";
import "./globals.css";
import SkipLink from "./components/SkipLink";

export const metadata: Metadata = {
  title: "LiMa 量子星云系统",
  description:
    "LiMa 量子星云系统是 AI 量子化设备调度平台，以量子路由、多模态坍缩与设备纠缠协同，连接 170+ AI 后端，驱动 AI 绘图机、写字机与 2D 数字人完成真实创作。",
  keywords: ["LiMa", "AI", "量子路由", "AI 绘图机", "AI 写字机", "2D 数字人", "OpenAI API"],
  openGraph: {
    title: "LiMa 量子星云系统",
    description: "把自然语言坍缩为真实创作",
    url: "https://www.donglicao.com",
    type: "website",
    images: ["https://www.donglicao.com/assets/hero.jpg"],
  },
  twitter: {
    card: "summary_large_image",
    title: "LiMa 量子星云系统",
    description: "把自然语言坍缩为真实创作",
    images: ["https://www.donglicao.com/assets/hero.jpg"],
  },
  alternates: {
    canonical: "https://www.donglicao.com",
  },
  other: {
    "theme-color": "#07070f",
  },
};

const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      name: "LiMa 量子星云",
      url: "https://www.donglicao.com",
      description: "把自然语言坍缩为真实创作",
    },
    {
      "@type": "Organization",
      name: "深圳市动力巢科技有限公司",
      url: "https://www.donglicao.com",
      logo: "https://www.donglicao.com/assets/hero.jpg",
      sameAs: ["https://github.com/zhuguang-ZFG/QWEN3.0"],
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <head>
        <link rel="preconnect" href="https://www.donglicao.com" crossOrigin="anonymous" />
        <link rel="dns-prefetch" href="https://www.donglicao.com" />
        <link rel="preload" as="image" href="/assets/hero.webp" type="image/webp" />
      </head>
      <body className="min-h-full flex flex-col bg-[#07070f] text-slate-200">
        <SkipLink />
        {children}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
        />
      </body>
    </html>
  );
}
