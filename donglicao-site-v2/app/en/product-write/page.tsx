import type { Metadata } from "next";
import ProductPage from "../../components/ProductPage";
import Icon from "../../components/Icon";

export const metadata: Metadata = {
  title: "AI Writing Machine - LiMa Quantum Nebula",
  description:
    "LiMa AI Writing Machine converts digital text into real handwriting for letters, cards, signatures and bulk mail.",
  alternates: { canonical: "https://donglicao.com/en/product-write/" },
};

export const dynamic = "force-static";

const enLabels = {
  ctaTry: "Try online",
  ctaDocs: "Read docs",
  coreTitle: "Core capabilities",
  coreSubtitle: "From digital text to warm handwritten output.",
  specsTitle: "Specifications",
  specsSubtitle: "Hardware and performance reference for procurement and integration.",
  scenariosTitle: "Use cases",
  scenariosSubtitle: "Real value already delivered in these scenarios.",
  faqTitle: "FAQ",
};

export default function ProductWriteEn() {
  return (
    <ProductPage
      eyebrow="AI Writing Machine"
      title="AI Writing Machine"
      highlight="Give text a human touch"
      description="Turn digital copy, greeting cards, signatures or bulk letters into real handwriting. LiMa supports style transfer, paper templates and personalized fonts so every letter feels hand-written."
      heroImage="/assets/product-write.webp"
      accent="#8b5cf6"
      labels={enLabels}
      features={[
        {
          icon: <Icon name="type" />,
          title: "Style transfer",
          desc: "Upload 20+ handwriting samples to train a personal font in the cloud and reproduce your own stroke.",
        },
        {
          icon: <Icon name="fileText" />,
          title: "Templates",
          desc: "Supports ruled, grid, blank and greeting-card templates with automatic line spacing and margins.",
        },
        {
          icon: <Icon name="layers" />,
          title: "Batch jobs",
          desc: "Import recipient lists and variables to generate and write multiple personalized letters at once.",
        },
        {
          icon: <Icon name="clock" />,
          title: "Scheduled execution",
          desc: "Schedule writing tasks and use off-peak queues to make the most of idle device time.",
        },
      ]}
      specs={[
        ["Effective writing area", "A4 / A5 / custom (max 220mm × 320mm)"],
        ["Writing tools", "Gel / fountain / marker pens (swappable holders)"],
        ["Protocols", "MQTT / WebSocket / local serial"],
        ["Inputs", "Plain text, Markdown, CSV variables, Word documents"],
        ["Font sources", "System fonts / user upload / AI-generated handwriting"],
        ["Batch limit", "Up to 1,000 letters per task"],
      ]}
      scenarios={[
        {
          icon: <Icon name="mail" />,
          title: "Business mail",
          desc: "Bulk generate thank-you notes, invitations and holiday cards with personal signatures.",
        },
        {
          icon: <Icon name="pencil" />,
          title: "Education",
          desc: "Generate copybooks, error notebooks or sample notes to help students practice handwriting.",
        },
        {
          icon: <Icon name="smile" />,
          title: "Gift customization",
          desc: "Present blessings or love letters in handwritten form with matching stationery and envelopes.",
        },
      ]}
      faqs={[
        {
          q: "How many handwriting samples are needed?",
          a: "We recommend 20-50 clear, evenly lit common characters. More samples produce more natural output.",
        },
        {
          q: "Which languages are supported?",
          a: "Chinese, English, numbers and common punctuation. Other languages can be added by uploading corresponding character samples.",
        },
        {
          q: "Can it simulate different stroke weights?",
          a: "Yes. The system adjusts trajectories based on pressure curves and the selected pen tip, and swappable pen holders enable weight variation.",
        },
        {
          q: "What if a batch task fails?",
          a: "LiMa records the status of each letter. Failed items can be retried individually or exported as a failure list without restarting the whole batch.",
        },
      ]}
    />
  );
}
