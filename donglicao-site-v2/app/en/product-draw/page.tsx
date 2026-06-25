import type { Metadata } from "next";
import ProductPage from "../../components/ProductPage";
import Icon from "../../components/Icon";

export const metadata: Metadata = {
  title: "AI Drawing Machine - LiMa Quantum Nebula",
  description:
    "LiMa AI Drawing Machine turns prompts into vector line art and drives a physical plotter via a single API.",
  alternates: { canonical: "https://donglicao.com/en/product-draw/" },
};

export const dynamic = "force-static";

const enLabels = {
  ctaTry: "Try online",
  ctaDocs: "Read docs",
  coreTitle: "Core capabilities",
  coreSubtitle: "From prompt to physical stroke, fully automated.",
  specsTitle: "Specifications",
  specsSubtitle: "Hardware and performance reference for procurement and integration.",
};

export default function ProductDrawEn() {
  return (
    <ProductPage
      eyebrow="AI Drawing Machine"
      title="AI Drawing Machine"
      highlight="Draw imagination into reality"
      description="Generate vector illustrations, engineering sketches or art from a single sentence. LiMa picks the best image model through quantum routing and streams SVG paths to the plotter in real time."
      heroImage="/assets/product-draw.webp"
      accent="#06b6d4"
      labels={enLabels}
      features={[
        {
          icon: <Icon name="route" />,
          title: "Quantum routing",
          desc: "Automatically selects the best image backend from 170+ options based on style, cost and real-time health.",
        },
        {
          icon: <Icon name="image" />,
          title: "SVG vectorization",
          desc: "Outputs infinitely scalable vector paths suitable for different paper sizes, engraving or cutting.",
        },
        {
          icon: <Icon name="grid" />,
          title: "Multi-machine collaboration",
          desc: "Large artworks are automatically split across up to 16 plotters and seamlessly stitched together.",
        },
        {
          icon: <Icon name="shield" />,
          title: "Safe simulation",
          desc: "Paths are simulated in the cloud before drawing to avoid out-of-bounds moves or canvas damage.",
        },
      ]}
      specs={[
        ["Effective drawing area", "A3 / A4 / custom (max 420mm × 300mm)"],
        ["Drive", "Dual-axis stepper motors + GRBL controller"],
        ["Protocols", "MQTT / WebSocket / local serial"],
        ["Inputs", "Text prompt, SVG, PNG outline, sketch reference"],
        ["Cloud models", "Stable Diffusion / DALL·E / Recraft / custom"],
        ["Collaboration", "Up to 16 devices per task"],
      ]}
    />
  );
}
