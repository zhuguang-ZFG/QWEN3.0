# PRD — UI 优化:小程序 + chat-web 布局重构与交互打磨(2026-07-20)

## 背景与约束

用户方向(已确认):**保留两侧现有色系**(小程序克制青绿 #2dd4a7、chat-web 青/紫玻璃拟态),
重构布局与交互,**交互与可用性优先**,两侧并行。

调研清单(逐项含 文件:行号 + 具体改法):
- `research/chatweb-ui-inventory.md`(编号 T0-W* / W*)
- `research/mobile-ui-inventory.md`(编号 T0-M* / M*)

硬约束:
1. **不引入新色、不改 token 值**——只用既有 token 与工具类(两侧都备好了 .skeleton 等基础设施但没人用)。
2. 不改路由/页面骨架/功能语义;纯前端表现层 + 交互层。
3. 我方无实时视觉反馈:所有改动必须过编译/语法门禁;像素级美感由用户逐页验收,可逐项 revert。

## 范围(按层承诺)

### Tier 0 — 可见破损(必须,发布级)

- [x] T0-W1 `--accent-2` 未定义(devices/handwriting 三处主视觉失效)→ var(--violet)
- [x] T0-W2 voice-call `--violet` 未定义(通话中主按钮消失)→ 本页 :root 补值
- [x] T0-W3 devices/handwriting/usage 移动端导航死路 → 补 menu-toggle + overlay
- [x] T0-W4 playground ≤900px Monaco 高度塌缩 → min-height:240px
- [x] T0-M1 配网状态条浅色 Bootstrap 补丁 → --amber-g/--green-g

### Tier 1 — 交互态与高价值重构(必须)

**chat-web**(详见 research 清单对应编号):
- [x] W5 输入框文字遮挡 + 移动端 pill 图标化
- [x] W6 Enter 流式中误取消(一行守卫)
- [x] W7 停止生成可见 affordance(方形停止图标)
- [x] W8 流式滚动:近底才自动滚 + "回到最新"pill
- [x] W9 375px topbar 溢出
- [x] W10 首 token 前 skeleton + 流式光标 ▍
- [x] W11 聊天错误气泡可重试 + 网络/HTTP 分文案
- [x] W22 设备页 skeleton + 失败页内重试
- [x] W23 绑定/解绑按钮防重复 + loading 文案
- [x] W24 抽屉背景不透明化
- [x] W26 设备空态给直接按钮
- [x] W28 手写生成中按钮 spinner + 结果区 skeleton
- [x] W29/W30 手写无设备禁用+引导;失败可重试保留旧预览
- [x] W33/W34 auth 密码可见切换 + turnstile min-height 防跳动
- [x] W38 playground Key 改 password + 眼睛切换
- [x] W42-W46 voice-call:连接中脉冲、错误就近+指引、结束按钮默认禁用、返回入口+aria、通话中禁 select
- [x] W49 usage 空/错隐藏图表 + 加载 skeleton

**小程序**(详见 research 清单对应编号):
- [x] M2 详情页 skeleton(激活死 prop infoLoading)
- [x] M3 详情页折叠分组(transfer/share/日志/danger 收 wd-collapse)
- [x] M4 task-status 反馈中枢(空态/running 高亮/枚举本地化/failed 原因+重试)
- [x] M5 transfer-panel 双态重构(藏 transferId)
- [x] M6+M28+M10 敏感操作确认补齐:转让三操作、快捷暂停、接受转让、回原点、share 撤销(M23 项内)、
      voice 拒绝(M16 内)
- [x] M7 分享 token 可复制(现在事实不可用)
- [x] M11 WS 断开横幅 + 重连按钮
- [x] M12 supplies 两行 telemetry + 按钮收敛
- [x] M13 自检 loading 行 + 离线禁用
- [x] M14/M15 gallery 删除可发现 + 空态引导
- [x] M16 voice-approval 参数人话化 + per-task loading
- [x] M17 voice-stream 录音中视觉 + 识别中过渡
- [x] M18 write-draw busy 改 amber 语义
- [x] M27 列表骨架屏
- [x] M29 离线/忙快捷键入口 guard + per-key spinner(以现代码为准,round2 可能已部分修)
- [x] M30/M31 列表空态语义修正 + 失败页内重试
- [x] M38-M40 配网:扫描 loading、结果条(成功 checklist/失败重试)、disabled 原因文案

### Tier 2 — 一致性清扫(尽力,未完成项记录遗留)

- [x] W50 三页公共按钮类下沉 pages.css 单一来源;W51 .toast 双定义合并
- [x] W13/W14/W15/W17 触控目标/语音草稿快照/modal a11y/侧栏设备 skeleton
- [x] M8 info-card 去大渐变(与 M34 登录页渐变二选一,保留登录页为唯一例外)
- [x] M9 .bento-card/.bento-title 全局统一(删 10 份重复定义)
- [x] M34/M35/M20/M22/M23/M19/M41 硬编码色→token 清扫(settings 已清;login/voiceprint 等若有残留见 research 低优先)
- [ ] M36 voiceprint 直角卡补圆角;M45 privacy 复用 SectionCard — **遗留**

### 不修(记录)

低优先小项(W19-W21/W27/W31/W32/W35-W37/W39-W41/W47/W48、M21/M24-M26/M32/M33/M37/M42-M44/M46/M47):
留日常迭代,清单已在 research 文档中留档。

## 验收标准

- [x] AC1 Tier 0 五项全部修复,肉眼可验(用户逐页看)。
- [x] AC2 Tier 1 全部落地;Tier 2 尽力,未完成项在收尾时列出(M36/M45)。
- [ ] AC3 门禁:小程序 `npx vue-tsc --noEmit` 0 error(**发版前补跑**);chat-web 改动 .js `node --check` 全绿;
      vm 共享上下文/dist 重建发版前补。
- [x] AC4 不引入新色/新 token 值(仅复用既有 token)。
- [x] AC5 敏感操作(转让/暂停/接受/回原点/撤销分享/拒绝审批)全部有二次确认。
- [ ] AC6 用户视觉验收:提供逐页改动摘要清单供对照;任何不满意项可单项 revert。

## 审查闭环(2026-07-20)

见 `docs/reviews/2026-07-20-ui-polish-code-review.md`：W1–W3 + S1–S6 已修。

## 硬门禁

vue-tsc 0 error;node --check 全绿;不动后端;不动 e2e 契约字段(class 名重构不影响测试断言——
改前 grep `tests/ci/test_manager_mobile_*` 的字符串断言,被断言的 class/文案不得改名)。
