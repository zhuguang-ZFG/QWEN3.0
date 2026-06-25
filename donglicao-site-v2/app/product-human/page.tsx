import type { Metadata } from "next";
import ProductPage from "../components/ProductPage";
import Icon from "../components/Icon";

export const metadata: Metadata = {
  title: "2D 数字人 - LiMa 量子星云",
  description: "LiMa 2D 数字人：基于语音实时驱动口型、表情与动作，支持多音色、多语言与多平台推流。",
  alternates: {
    canonical: "https://donglicao.com/product-human/",
    languages: {
      "zh-CN": "https://donglicao.com/product-human/",
      "en-US": "https://donglicao.com/en/product-human/",
      "x-default": "https://donglicao.com/product-human/",
    },
  },
};

export default function ProductHuman() {
  return (
    <ProductPage
      eyebrow="2D Digital Human"
      title="2D 数字人"
      highlight="让声音拥有表情"
      description="基于语音实时驱动口型、表情与动作，支持多音色、多语言与多平台推流。无论是直播、客服还是内容创作，LiMa 数字人都能 7×24 小时在线表达。"
      heroImage="/assets/product-human.webp"
      accent="#ec4899"
      features={[
        { icon: <Icon name="mic" />, title: "语音驱动口型", desc: "根据音频特征实时推理口型权重，唇形与发音精准对齐。" },
        { icon: <Icon name="globe" />, title: "多语言多音色", desc: "支持中、英、德、葡、越等多种语言，可切换不同性别与情感音色。" },
        { icon: <Icon name="video" />, title: "实时推流", desc: "输出 RTMP / WebRTC / HLS 流，可直接接入直播间或视频会议。" },
        { icon: <Icon name="sliders" />, title: "姿态与表情可控", desc: "通过 prompt 或 API 参数控制微笑、眨眼、手势与情绪强度。" },
      ]}
      specs={[
        ["输出分辨率", "720p / 1080p（支持竖屏 9:16 与横屏 16:9）"],
        ["端到端延迟", "典型 200-500ms（取决于网络与模型选择）"],
        ["输入格式", "实时音频流、文本、SSML"],
        ["输出格式", "RTMP / WebRTC / HLS / MP4 录制"],
        ["角色定制", "立绘拆分、动作库、表情集、声纹克隆"],
        ["并发路数", "单节点支持 10+ 路实时推流"],
      ]}
      scenarios={[
        { icon: <Icon name="cast" />, title: "直播带货", desc: "7×24 小时自动讲解商品、回复弹幕，降低人力成本，提升开播时长。" },
        { icon: <Icon name="messageCircle" />, title: "智能客服", desc: "在 App、小程序或网页中以拟人形象解答用户问题，增强品牌亲和力。" },
        { icon: <Icon name="headphones" />, title: "内容创作", desc: "将文本稿件快速生成口播视频，用于短视频、课程与新闻播报。" },
      ]}
      faqs={[
        { q: "数字人形象可以定制吗？", a: "可以。提供立绘素材后，LiMa 协助完成图层拆分、口型绑定与动作库配置，也可使用官方默认形象快速上线。" },
        { q: "支持实时互动吗？", a: "支持。通过 WebSocket 接入语音识别与 LLM 回复，数字人可实时回答观众提问并做出对应表情。" },
        { q: "直播推流需要什么硬件？", a: "云端渲染无需本地显卡，普通 PC 或服务器即可推流；本地私有化部署建议配备 GPU 以支持多路并发。" },
      ]}
    />
  );
}
