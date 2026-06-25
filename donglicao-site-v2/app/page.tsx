import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import Products from "./components/Products";
import Technology from "./components/Technology";
import Scenarios from "./components/Scenarios";
import Testimonials from "./components/Testimonials";
import Developer from "./components/Developer";
import Partners from "./components/Partners";
import Footer from "./components/Footer";

export default function Home() {
  return (
    <>
      <Navbar />
      <main id="main" className="flex-1">
        <Hero />
        <Products />
        <Technology />
        <Scenarios />
        <Testimonials />
        <Developer />
        <Partners />
      </main>
      <Footer />
    </>
  );
}
