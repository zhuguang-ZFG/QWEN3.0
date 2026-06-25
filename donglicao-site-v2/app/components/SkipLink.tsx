export default function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-full focus:bg-cyan-500 focus:px-4 focus:py-2 focus:text-slate-950"
    >
      跳到主要内容
    </a>
  );
}
