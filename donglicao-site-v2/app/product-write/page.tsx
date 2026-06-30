import type { Metadata } from "next";
import ProductPage from "../components/ProductPage";
import Icon from "../components/Icon";

export const metadata: Metadata = {
  title: "AI 写字机 - LiMa 量子星云",
  description: "LiMa AI 写字机：将电子文案、贺卡、签名或批量信函转换为真实手写笔迹，支持字体迁移、纸张模板与个性化字库。",
  alternates: {
    canonical: "https://www.donglicao.com/product-write/",
    languages: {
      "zh-CN": "https://www.donglicao.com/product-write/",
      "en-US": "https://www.donglicao.com/en/product-write/",
      "x-default": "https://www.donglicao.com/product-write/",
    },
  },
};

export default function ProductWrite() {
  return (
    <ProductPage
      eyebrow="AI Writing Machine"
      title="AI 写字机"
      highlight="让文字有温度"
      description="将电子文案、贺卡、签名或批量信函转换为真实手写笔迹。LiMa 支持字体迁移、纸张模板与个性化字库，让每一封信都像是亲手所写。"
      heroImage="/assets/product-write.webp"
      accent="#8b5cf6"
      features={[
        { icon: <Icon name="type" />, title: "字体迁移", desc: "上传 20 字以上手写样本，云端训练专属字库，复刻个人笔迹。" },
        { icon: <Icon name="fileText" />, title: "模板信纸", desc: "支持横线、方格、空白、贺卡等多种模板，自动对齐行距与边距。" },
        { icon: <Icon name="layers" />, title: "批量任务", desc: "一次导入收件人列表与变量，自动生成并书写多份个性化信件。" },
        { icon: <Icon name="clock" />, title: "预约执行", desc: "支持定时书写与错峰队列，避免高峰排队，充分利用设备空闲时段。" },
      ]}
      specs={[
        ["有效书写面积", "A4 / A5 / 自定义（最大 220mm × 320mm）"],
        ["书写工具", "中性笔 / 钢笔 / 马克笔（可换夹具）"],
        ["通信协议", "MQTT / WebSocket / 本地串口"],
        ["支持输入", "纯文本、Markdown、CSV 变量、Word 文档"],
        ["字体来源", "系统字体 / 用户上传 / AI 生成笔迹"],
        ["批量上限", "单次任务最多 1000 封信件"],
      ]}
      scenarios={[
        { icon: <Icon name="mail" />, title: "商务信函", desc: "批量生成带个人签名的感谢信、邀请函与节日贺卡，提升客户感知。" },
        { icon: <Icon name="pencil" />, title: "教育练习", desc: "生成字帖、错题本或笔记样本，帮助学生进行书写练习与临摹。" },
        { icon: <Icon name="smile" />, title: "礼品定制", desc: "将祝福语或情书以手写形式呈现，搭配信纸与信封，适合送礼场景。" },
      ]}
      faqs={[
        { q: "需要多少手写样本来训练字库？", a: "建议提供 20-50 个常用汉字，字迹清晰、光线均匀。样本越多，生成笔迹越自然。" },
        { q: "支持哪些语言？", a: "中文、英文、数字与常见标点。其他语言可通过上传对应字符样本扩展。" },
        { q: "可以模拟不同笔迹粗细吗？", a: "可以。系统会根据字体压力曲线与所选笔尖参数调整轨迹，配合可换笔夹实现粗细变化。" },
        { q: "批量任务出错怎么办？", a: "LiMa 会逐封信件记录执行状态，失败项可单独重试或导出失败清单，无需从头开始。" },
      ]}
    />
  );
}
