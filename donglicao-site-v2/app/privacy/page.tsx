// ponytail: legal body text is hardcoded per-locale in JSX. Ceiling: 2 locales
// (zh/en). Upgrade path: single JSON/MD source per locale rendered via a shared
// component when a 3rd locale lands.
import type { Metadata } from "next";
import LegalPage from "../components/LegalPage";

export const metadata: Metadata = {
  title: "隐私政策 - LiMa 量子星云系统",
  description: "LiMa 量子星云系统隐私政策：我们如何收集、使用、存储和保护你的信息。",
  alternates: {
    canonical: "https://www.donglicao.com/privacy/",
    languages: {
      "zh-CN": "https://www.donglicao.com/privacy/",
      "en-US": "https://www.donglicao.com/en/privacy/",
      "x-default": "https://www.donglicao.com/privacy/",
    },
  },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="隐私政策">
      <p>
        <strong>最后更新日期：</strong>2026 年 6 月 25 日
      </p>
      <p>
        深圳市动力巢科技有限公司（以下简称“我们”或“动力巢”）重视用户的隐私保护。本隐私政策说明 LiMa
        量子星云系统（以下简称“本服务”）如何收集、使用、存储和保护你的信息。
      </p>

      <h2>1. 信息收集</h2>
      <p>为提供路由、设备协同与客户支持服务，我们可能会收集：</p>
      <ul>
        <li>账户信息：邮箱、用户名、企业名称等注册信息；</li>
        <li>使用数据：API 请求量、设备状态、错误日志；</li>
        <li>设备信息：设备标识、固件版本、连接方式；</li>
        <li>支付信息：由第三方支付平台处理，我们不会直接存储完整银行卡号。</li>
      </ul>

      <h2>2. 信息使用</h2>
      <p>我们使用收集的信息用于：提供服务、优化模型路由、保障系统安全、处理账单与售后、发送服务通知。</p>

      <h2>3. 信息共享</h2>
      <p>
        我们不会向第三方出售你的个人信息。仅在以下情形共享：获得你的同意、法律法规要求、与服务提供商（如云服务商、支付渠道）在必要范围内共享。
      </p>

      <h2>4. 信息安全</h2>
      <p>
        我们采用 TLS 加密传输、访问控制、审计日志等技术手段保护数据安全。但请你理解，没有任何网络服务能保证绝对安全。
      </p>

      <h2>5. 你的权利</h2>
      <p>
        你可以登录控制台查看、修改或删除部分个人信息。如需注销账户或行使其他权利，请联系{" "}
        <a href="mailto:support@donglicao.com">support@donglicao.com</a>。
      </p>

      <h2>6. 政策更新</h2>
      <p>我们可能会不时更新本政策。更新后的政策将在本页面发布，重大变更会通过服务通知告知你。</p>

      <p>
        如有疑问，请发送邮件至 <a href="mailto:support@donglicao.com">support@donglicao.com</a>。
      </p>
    </LegalPage>
  );
}
