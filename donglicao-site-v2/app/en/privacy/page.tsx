import type { Metadata } from "next";
import LegalPage from "../../components/LegalPage";

export const metadata: Metadata = {
  title: "Privacy Policy - LiMa Quantum Nebula",
  description:
    "LiMa Quantum Nebula privacy policy: how we collect, use, store, and protect your information.",
  alternates: {
    canonical: "https://donglicao.com/en/privacy/",
    languages: {
      "en-US": "https://donglicao.com/en/privacy/",
      "zh-CN": "https://donglicao.com/privacy/",
      "x-default": "https://donglicao.com/privacy/",
    },
  },
};

export const dynamic = "force-static";

export default function PrivacyEnPage() {
  return (
    <LegalPage title="Privacy Policy">
      <p>
        <strong>Last updated:</strong> June 25, 2026
      </p>
      <p>
        Shenzhen Donglichao Technology Co., Ltd. (“we”, “us”, or “Donglichao") respects your privacy.
        This Privacy Policy explains how LiMa Quantum Nebula (the “Service") collects, uses, stores,
        and protects your information.
      </p>

      <h2>1. Information we collect</h2>
      <p>To provide routing, device collaboration, and customer support, we may collect:</p>
      <ul>
        <li>Account information: email, username, company name, and other registration details;</li>
        <li>Usage data: API request volume, device status, and error logs;</li>
        <li>Device information: device identifier, firmware version, and connection method;</li>
        <li>
          Payment information: handled by third-party payment processors. We do not store complete
          bank card numbers.
        </li>
      </ul>

      <h2>2. How we use information</h2>
      <p>
        We use the information we collect to provide and improve the Service, optimize model routing,
        ensure system security, process billing and support requests, and send service notifications.
      </p>

      <h2>3. Information sharing</h2>
      <p>
        We do not sell your personal information. We only share it when: we have your consent, we are
        required by law, or we need to share it with service providers (such as cloud and payment
        providers) to the extent necessary to operate the Service.
      </p>

      <h2>4. Information security</h2>
      <p>
        We protect data with TLS encryption, access controls, and audit logs. However, no internet
        service can guarantee absolute security.
      </p>

      <h2>5. Your rights</h2>
      <p>
        You can view, modify, or delete some personal information in the console. To delete your
        account or exercise other rights, contact{" "}
        <a href="mailto:support@donglicao.com">support@donglicao.com</a>.
      </p>

      <h2>6. Policy updates</h2>
      <p>
        We may update this policy from time to time. Updates will be posted on this page, and material
        changes will be communicated through service notifications.
      </p>

      <p>
        If you have any questions, please email{" "}
        <a href="mailto:support@donglicao.com">support@donglicao.com</a>.
      </p>
    </LegalPage>
  );
}
