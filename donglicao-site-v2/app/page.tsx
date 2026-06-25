import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import Products from "./components/Products";
import Technology from "./components/Technology";
import Scenarios from "./components/Scenarios";
import Testimonials from "./components/Testimonials";
import Developer from "./components/Developer";
import Partners from "./components/Partners";
import Footer from "./components/Footer";
import Reveal from "./components/Reveal";

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
      </main>
      <Footer />
    </>
  );
}
