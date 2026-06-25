import type { Metadata } from "next";
import Link from "next/link";
import Navbar from "../../components/Navbar";
import Footer from "../../components/Footer";
import { posts } from "../posts";

export const dynamic = "force-static";

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return posts.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = posts.find((p) => p.slug === slug);
  if (!post) return { title: "文章未找到" };
  return {
    title: `${post.title} - LiMa 博客`,
    description: post.excerpt,
    openGraph: { title: post.title, description: post.excerpt },
  };
}

export default async function BlogPost({ params }: Props) {
  const { slug } = await params;
  const post = posts.find((p) => p.slug === slug);
  if (!post) {
    return (
      <>
        <Navbar />
        <main id="main" className="flex-1 px-6 py-24 text-center">
          <h1 className="text-2xl font-bold text-slate-50">文章未找到</h1>
          <Link href="/blog/" className="mt-4 inline-block text-cyan-400 hover:text-cyan-300">
            返回博客列表
          </Link>
        </main>
        <Footer />
      </>
    );
  }

  const structuredData = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.excerpt,
    author: { "@type": "Organization", name: post.author },
    datePublished: post.date,
  };

  return (
    <>
      <Navbar />
      <main id="main" className="flex-1 px-6 py-24">
        <article className="mx-auto max-w-3xl">
          <Link href="/blog/" className="text-sm text-cyan-400 hover:text-cyan-300">
            ← 返回博客列表
          </Link>
          <h1 className="mt-4 text-3xl font-bold text-slate-50 md:text-4xl">{post.title}</h1>
          <div className="mt-3 flex items-center gap-3 text-sm text-slate-500">
            <time dateTime={post.date}>{post.date}</time>
            <span>·</span>
            <span>{post.author}</span>
          </div>

          <div className="prose prose-invert mt-8 max-w-none">
            {post.content.map((paragraph, index) => (
              <p key={index} className="mb-5 leading-relaxed text-slate-300">
                {paragraph}
              </p>
            ))}
          </div>
        </article>
      </main>
      <Footer />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
    </>
  );
}
