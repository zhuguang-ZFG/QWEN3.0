import Navbar from "./Navbar";
import Footer from "./Footer";

interface LegalPageProps {
  title: string;
  children: React.ReactNode;
}

export default function LegalPage({ title, children }: LegalPageProps) {
  return (
    <>
      <Navbar />
      <main id="main" className="flex-1 px-6 pt-32 pb-20">
        <div className="mx-auto max-w-3xl">
          <div className="mb-10 text-center">
            <div className="mb-3 text-xs font-medium uppercase tracking-wider text-cyan-400">Legal</div>
            <h1 className="text-3xl font-bold text-slate-50 md:text-4xl">{title}</h1>
          </div>
          <div className="legal-content space-y-6 text-slate-300">
            {children}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
