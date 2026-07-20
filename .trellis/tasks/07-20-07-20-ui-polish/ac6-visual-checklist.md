# AC6 视觉验收清单 — UI polish（2026-07-20）

> 对照改动页快速扫一眼即可。色系保持克制青绿深色（`--accent` / `#2dd4a7`），不引入新色。

## chat-web

| 页 | 应看到 | 不该看到 |
|----|--------|----------|
| `index.html` 聊天 | 流式中有 skeleton；停止后 partial 保留或「已停止」；失败可重试且不叠气泡 | 流式中切会话后新会话出现旧 token / 错图 |
| 侧栏历史 | 点会话切换正常；流式中切换会中止生成 | 会话列表串内容 |
| `devices.html` | 顶栏 menu-toggle；列表 skeleton；刷新失败有缓存时只 banner | 失败 + 缓存双 UI |
| `handwriting.html` | menu-toggle；按钮 spinner 本地样式 | 浅色补丁色 |
| `usage.html` | menu-toggle；图表区有守卫 | 无菜单按钮 |
| `playground.html` | 最小高度 ≥240px；历史可删 | 区域塌缩 |
| `voice-call.html` | `--violet` 生效；错误在状态行；结束通话清 error | 麦克风连击泄漏（需实机） |
| `login` / `register` | Turnstile 冷加载可渲染 | 永久卡死 |

## 小程序 manager-mobile

| 页 | 应看到 | 不该看到 |
|----|--------|----------|
| 设备列表 | skeleton 卡；暂停/接受转让有确认 | 离线仍可误发（已有守卫） |
| 设备详情 | 高级区折叠；task-status 本地化 + 失败重试；分享可复制 | 浅黄/浅绿 Bootstrap 补丁 |
| 写画面板 | busy 用 amber 文案「设备忙碌中」 | 红色 busy 过重 |
| 声纹 `voiceprint` | **圆角 24rpx** 卡片（M36） | 全直角卡 |
| 设置 `settings` | SectionCard 统一壳 | 危险按钮两套形态混用 |
| 隐私权限 | **SectionCard** 分区（M45） | 第三套独立卡片壳 |
| 配网 Wi-Fi | 状态色 token；失败结果条 | `#fff3cd` / `#d4edda` |

## 残留（非阻断）

- Tier2 低优先：见 `docs/reviews/2026-07-20-tech-debt-backlog.md` chat-web / 小程序段
- 真机：voice-call AudioWorklet、WDT HIL（`07-20-u8-wdt-panic-hil`）
