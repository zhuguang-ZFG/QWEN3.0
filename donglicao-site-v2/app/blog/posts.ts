export interface Post {
  slug: string;
  title: string;
  date: string;
  author: string;
  excerpt: string;
  content: string[];
}

export const posts: Post[] = [
  {
    slug: "welcome-to-lima",
    title: "欢迎来到 LiMa 量子星云",
    date: "2026-06-25",
    author: "LiMa 团队",
    excerpt:
      "LiMa 是一个多后端 AI 路由与智能设备云平台。本文带你快速了解它的核心能力、典型场景与下一步计划。",
    content: [
      "LiMa（LiMa 量子星云）把 170+ AI 后端统一调度到一次 API 调用中。无论是 GPT-4o、Claude、DeepSeek，还是 Groq、NVIDIA、OpenRouter，你都可以通过同一个 OpenAI 兼容端点按需使用。",
      "除了对话能力，LiMa 还是 AI 绘画机、AI 写字机与 2D 数字人的云端大脑。设备通过 ESP32 接入，支持 OTA 升级、远程证明、任务队列与实时状态同步。",
      "对于开发者，LiMa 提供 VitePress 文档站、OpenAPI 参考、Redoc 渲染以及 Python / JavaScript / Go 官方 SDK。控制台与 API Playground 让你可以在线调试流式响应。",
      "未来我们会继续补齐多语言官网、管理面板、规则引擎与 RAG 知识库。感谢关注，敬请期待。",
    ],
  },
  {
    slug: "build-first-ai-device",
    title: "三步构建你的第一个 AI 设备",
    date: "2026-06-20",
    author: "LiMa 团队",
    excerpt:
      "从固件编译到设备绑定，再到下发第一个绘画任务，本文帮你理清端到端的接入路径。",
    content: [
      "第一步，准备硬件。LiMa 当前主要支持 ESP32-S3 / ESP32-C3 开发板。你可以从 reference/hardware 找到 u1-grbl 绘图机、u8-xiaozhi 语音助手与 2D 数字人的参考接线图。",
      "第二步，编译并烧录固件。仓库提供 platformio 工程与 Docker 编译环境。烧录后，设备会在启动时向 LiMa 注册，并在控制台显示为“待绑定”状态。",
      "第三步，绑定并创作。在控制台或小程序输入设备上的绑定码，即可将设备加入账号。随后打开对话页，输入“画一只猫”，LiMa 会自动选择合适后端生成 SVG 并发往设备绘制。",
      "更复杂的创作流程支持模板、任务进度条、语音输入与素材库。如果遇到问题，可以访问 docs.donglicao.com 查阅完整文档。",
    ],
  },
  {
    slug: "coding-capability-retirement",
    title: "编码能力退役说明",
    date: "2026-06-18",
    author: "LiMa 团队",
    excerpt:
      "出于维护成本与质量稳定性考虑，LiMa 已正式退役 IDE/编码场景的路由与上下文流水线。",
    content: [
      "在早期的实验阶段，LiMa 曾支持基于 tree-sitter 的代码上下文扫描、编码质量验证与 IDE 场景路由。随着模型能力的演进，通用聊天后端已经能够稳定处理大多数代码问题，而专用编码路径的维护成本持续上升。",
      "因此，我们从 v1.3 起移除了 `context_pipeline/code_context_injection` 的默认启用，并归档了相关设计文档。服务器端核心路由、设备网关、会话记忆与多模态生成能力不受影响。",
      "如果你仍需要在对话中获得代码帮助，可以直接使用 `/v1/chat/completions` 端点，模型会根据 prompt 自动输出代码块。",
    ],
  },
];
