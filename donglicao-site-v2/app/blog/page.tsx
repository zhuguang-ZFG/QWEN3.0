import type { Metadata } from "next";
import Link from "next/link";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { posts } from "./posts";

export const metadata: Metadata = {
  title: "博客 - LiMa 量子星云",
  description: "LiMa 团队的产品更新、接入指南与技术洞察。",
};

export const dynamic = "force-static";

export default function BlogIndex() {
  return (
    <>
      <Navbar />
      <main id="main" className="flex-1 px-6 py-24">
        <div className="mx-auto max-w-4xl">
          <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Blog</div>
          <h1 className="text-3xl font-bold text-slate-50 md:text-4xl">LiMa 博客</h1>
          <p className="mt-2 text-slate-400">产品更新、接入指南与技术洞察。</p>

          <div className="mt-10 space-y-6">
            {posts.map((post) => (
              <article
                key={post.slug}
                className="rounded-xl border border-white/10 bg-white/[0.03] p-6 transition-colors hover:border-white/15 hover:bg-white/[0.05]"
              >
                <Link href={`/blog/${post.slug}/`} className="block">
                  <h2 className="text-xl font-semibold text-slate-100 hover:text-cyan-400">{post.title}</h2>
                </Link>
                <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                  <time dateTime={post.date}>{post.date}</time>
                  <span>·</span>
                  <span>{post.author}</span>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">{post.excerpt}</p>
                <Link
                  href={`/blog/${post.slug}/`}
                  className="mt-4 inline-block text-sm font-medium text-cyan-400 hover:text-cyan-300"
                >
                  阅读全文 →
                </Link>
              </article>
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
