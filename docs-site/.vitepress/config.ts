import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'LiMa 文档',
  description: 'LiMa 量子星云开发者文档',
  lang: 'zh-CN',
  base: '/docs/',
  appearance: 'force-dark',
  cleanUrls: true,
  lastUpdated: false,
  themeConfig: {
    nav: [
      { text: '指南', link: '/guide/getting-started' },
      { text: 'API', link: '/api/authentication' },
      { text: '设备', link: '/device/firmware-build' },
      { text: '更新日志', link: '/changelog/' },
    ],
    sidebar: {
      '/guide/': [
        {
          text: '新手上路',
          items: [
            { text: '5 分钟接入', link: '/guide/getting-started' },
            { text: '获取 API Key', link: '/guide/api-key' },
            { text: '第一个请求', link: '/guide/first-request' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API 文档',
          items: [
            { text: '认证方式', link: '/api/authentication' },
            { text: 'Chat Completions', link: '/api/chat-completions' },
            { text: '图像生成', link: '/api/image-generations' },
            { text: '设备控制', link: '/api/device-control' },
            { text: '语音交互', link: '/api/voice' },
            { text: '错误码', link: '/api/errors' },
            { text: 'OpenAPI 参考', link: '/api/reference' },
          ],
        },
      ],
      '/device/': [
        {
          text: '设备开发',
          items: [
            { text: '固件编译', link: '/device/firmware-build' },
            { text: 'Grbl 配置', link: '/device/grbl-config' },
            { text: 'OTA 升级', link: '/device/ota' },
            { text: '硬件参考', link: '/device/hardware' },
          ],
        },
      ],
      '/changelog/': [
        {
          text: '更新日志',
          items: [
            { text: '时间线', link: '/changelog/' },
            { text: 'Phase 5 小程序增强', link: '/changelog/2026-06-25-phase5' },
            { text: '编码能力退役', link: '/changelog/2026-06-24-coding-retirement' },
          ],
        },
      ],
    },
    search: {
      provider: 'local',
    },
    footer: {
      message: 'LiMa 量子星云 · 开发者文档',
      copyright: '© 2026 LiMa',
    },
  },
  vue: {
    template: {
      compilerOptions: {
        isCustomElement: (tag) => tag === 'redoc',
      },
    },
  },
})
