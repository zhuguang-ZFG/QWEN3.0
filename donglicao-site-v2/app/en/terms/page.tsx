// ponytail: legal body text is hardcoded per-locale in JSX. Ceiling: 2 locales
// (zh/en). Upgrade path: single JSON/MD source per locale rendered via a shared
// component when a 3rd locale lands.
import type { Metadata } from "next";
import LegalPage from "../../components/LegalPage";

export const metadata: Metadata = {
  title: "Terms of Service - LiMa Quantum Nebula",
  description: "LiMa Quantum Nebula terms of service.",
  alternates: {
    canonical: "https://donglicao.com/en/terms/",
    languages: {
      "en-US": "https://donglicao.com/en/terms/",
      "zh-CN": "https://donglicao.com/terms/",
      "x-default": "https://donglicao.com/terms/",
    },
  },
};

export const dynamic = "force-static";

export default function TermsEnPage() {
  return (
    <LegalPage title="Terms of Service">
      <p>
        <strong>Last updated:</strong> June 25, 2026
      </p>
      <p>
        Welcome to LiMa Quantum Nebula (the “Service"). These Terms of Service are entered into by
        you (“User") and Shenzhen Donglichao Technology Co., Ltd. (“we", “us", or “Donglichao").
        By accessing or using the Service, you agree to be bound by these terms.
      </p>

      <h2>1. Service description</h2>
      <p>
        LiMa Quantum Nebula provides AI routing, content generation, device collaboration, and related
        API services. We reserve the right to adjust, suspend, or terminate parts of the Service at any
        time.
      </p>

      <h2>2. Accounts and acceptable use</h2>
      <p>
        You are responsible for the security of your account. You may not transfer, lend, or share your
        account. You may not use the Service for illegal activities, to infringe on others&apos; rights, or
        to interfere with the normal operation of the system.
      </p>

      <h2>3. Intellectual property</h2>
      <p>
        The Service, related software, documentation, and trademarks are owned by us or our licensors.
        Your lawful outputs generated through the Service are governed by these terms and applicable
        laws.
      </p>

      <h2>4. Data and privacy</h2>
      <p>
        We collect and use your information in accordance with our{" "}
        <a href="/en/privacy/">Privacy Policy</a>. Please read it carefully.
      </p>

      <h2>5. Disclaimer</h2>
      <p>
        The Service is provided “as is”. We are not liable for service interruptions or data loss caused
        by network, device, third-party services, or force majeure, but we will make reasonable efforts
        to maintain availability.
      </p>

      <h2>6. Changes to the terms</h2>
      <p>
        We may modify these terms based on laws or business needs. Updated terms will be posted on this
        page, and continued use of the Service constitutes acceptance of the changes.
      </p>

      <h2>7. Contact us</h2>
      <p>
        If you have any questions, please email{" "}
        <a href="mailto:support@donglicao.com">support@donglicao.com</a>.
      </p>
    </LegalPage>
  );
}
