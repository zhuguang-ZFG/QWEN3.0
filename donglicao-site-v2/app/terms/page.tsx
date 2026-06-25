// ponytail: legal body text is hardcoded per-locale in JSX. Ceiling: 2 locales
// (zh/en). Upgrade path: single JSON/MD source per locale rendered via a shared
// component when a 3rd locale lands.
import type { Metadata } from "next";
import LegalPage from "../components/LegalPage";

export const metadata: Metadata = {
  title: "用户协议 - LiMa 量子星云系统",
  description: "LiMa 量子星云系统用户协议。",
  alternates: {
    canonical: "https://donglicao.com/terms/",
    languages: {
      "zh-CN": "https://donglicao.com/terms/",
      "en-US": "https://donglicao.com/en/terms/",
      "x-default": "https://donglicao.com/terms/",
    },
  },
};

export default function TermsPage() {
  return (
    <LegalPage title="用户协议">
      <p>
        <strong>最后更新日期：</strong>2026 年 6 月 25 日
      </p>
      <p>
        欢迎使用 LiMa 量子星云系统（以下简称“本服务”）。本协议由你（以下简称“用户”）与深圳市动力巢科技有限公司（以下简称“我们”）共同缔结。访问或使用本服务，即表示你同意受本协议约束。
      </p>

      <h2>1. 服务说明</h2>
      <p>
        LiMa 量子星云系统提供 AI 路由、内容生成、设备协同与相关 API 服务。我们保留随时调整、暂停或终止部分服务的权利。
      </p>

      <h2>2. 账户与使用规则</h2>
      <p>
        你需对账户安全负责，不得将账户转让、出借或共享。禁止利用本服务从事违法违规、侵犯他人权益或干扰系统正常运行的行为。
      </p>

      <h2>3. 知识产权</h2>
      <p>
        本服务及相关软件、文档、标识的知识产权归我们或相关权利人所有。用户在使用服务过程中产生的合法输出，其使用权按本协议及适用法律处理。
      </p>

      <h2>4. 数据与隐私</h2>
      <p>
        我们按照<a href="/privacy/">《隐私政策》</a>收集和使用你的信息。请你仔细阅读并理解隐私政策的内容。
      </p>

      <h2>5. 免责声明</h2>
      <p>
        本服务按“现状”提供，我们不对因网络、设备、第三方服务或不可抗力导致的服务中断或数据丢失承担责任，但会尽力保障服务可用性。
      </p>

      <h2>6. 协议修改</h2>
      <p>我们可能会根据法律法规或业务发展修改本协议。修改后的协议将在本页面公布，继续使用本服务视为接受修改。</p>

      <h2>7. 联系我们</h2>
      <p>
        如有任何问题，请发送邮件至 <a href="mailto:support@donglicao.com">support@donglicao.com</a>。
      </p>
    </LegalPage>
  );
}
