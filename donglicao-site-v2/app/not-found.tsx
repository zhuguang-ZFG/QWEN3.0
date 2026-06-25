import Link from "next/link";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";

export default function NotFound() {
  return (
    <>
      <Navbar />
      <main id="main" className="flex flex-1 flex-col items-center justify-center px-6 py-32 text-center">
        <div className="text-6xl font-bold text-cyan-400">404</div>
        <h1 className="mt-4 text-2xl font-semibold text-slate-100">页面未找到</h1>
        <p className="mt-2 text-slate-400">你访问的页面可能已经迁移或不存在。</p>
        <Link
          href="/"
          className="mt-6 rounded-full bg-cyan-500 px-6 py-2.5 font-semibold text-slate-950 hover:bg-cyan-400"
        >
          返回首页
        </Link>
      </main>
      <Footer />
    </>
  );
}
