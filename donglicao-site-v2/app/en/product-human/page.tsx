import type { Metadata } from "next";
import ProductPage from "../../components/ProductPage";
import Icon from "../../components/Icon";

export const metadata: Metadata = {
  title: "2D Digital Human - LiMa Quantum Nebula",
  description:
    "LiMa 2D Digital Human drives lip-sync, expression and motion from voice in real time for live streaming and customer service.",
  alternates: { canonical: "https://donglicao.com/en/product-human/" },
};

export const dynamic = "force-static";

const enLabels = {
  ctaTry: "Try online",
  ctaDocs: "Read docs",
  coreTitle: "Core capabilities",
  coreSubtitle: "From voice to expressive digital presence.",
  specsTitle: "Specifications",
  specsSubtitle: "Hardware and performance reference for procurement and integration.",
  scenariosTitle: "Use cases",
  scenariosSubtitle: "Real value already delivered in these scenarios.",
  faqTitle: "FAQ",
};

export default function ProductHumanEn() {
  return (
    <ProductPage
      eyebrow="2D Digital Human"
      title="2D Digital Human"
      highlight="Give voice a face"
      description="Drive lip-sync, expression and motion from voice in real time. Supports multiple voices, languages and streaming platforms. Whether for live commerce, customer service or content creation, your LiMa digital human can express 24/7."
      heroImage="/assets/product-human.webp"
      accent="#ec4899"
      labels={enLabels}
      features={[
        {
          icon: <Icon name="mic" />,
          title: "Voice-driven lipsync",
          desc: "Real-time lip weights inferred from audio features, precisely aligned with pronunciation.",
        },
        {
          icon: <Icon name="globe" />,
          title: "Multilingual & multi-voice",
          desc: "Supports Chinese, English, German, Portuguese, Vietnamese and more, with switchable gender and emotion voices.",
        },
        {
          icon: <Icon name="video" />,
          title: "Real-time streaming",
          desc: "Outputs RTMP / WebRTC / HLS streams ready for live rooms or video conferencing.",
        },
        {
          icon: <Icon name="sliders" />,
          title: "Controllable pose & expression",
          desc: "Control smiles, blinks, gestures and emotion intensity through prompts or API parameters.",
        },
      ]}
      specs={[
        ["Output resolution", "720p / 1080p (portrait 9:16 and landscape 16:9)"],
        ["End-to-end latency", "Typical 200-500ms depending on network and model"],
        ["Input formats", "Real-time audio stream, text, SSML"],
        ["Output formats", "RTMP / WebRTC / HLS / MP4 recording"],
        ["Customization", "Layered art, motion library, expression set, voice cloning"],
        ["Concurrent streams", "10+ real-time streams per node"],
      ]}
      scenarios={[
        {
          icon: <Icon name="cast" />,
          title: "Live commerce",
          desc: "Automatically present products and reply to bullet comments 24/7, reducing labor costs and extending broadcast hours.",
        },
        {
          icon: <Icon name="messageCircle" />,
          title: "Smart customer service",
          desc: "Answer user questions with a human-like avatar in apps, mini-programs or web pages.",
        },
        {
          icon: <Icon name="headphones" />,
          title: "Content creation",
          desc: "Quickly turn text scripts into talking-head videos for short videos, courses and news broadcasts.",
        },
      ]}
      faqs={[
        {
          q: "Can the avatar be customized?",
          a: "Yes. Provide layered artwork and LiMa helps with layer splitting, lip binding and motion library configuration. Default avatars are also available for quick launch.",
        },
        {
          q: "Does it support real-time interaction?",
          a: "Yes. Connect speech recognition and LLM replies via WebSocket so the avatar can answer audience questions with matching expressions in real time.",
        },
        {
          q: "What hardware is needed for streaming?",
          a: "Cloud rendering requires no local GPU; a regular PC or server can push the stream. On-premises deployment with GPU is recommended for multi-stream concurrency.",
        },
      ]}
    />
  );
}
