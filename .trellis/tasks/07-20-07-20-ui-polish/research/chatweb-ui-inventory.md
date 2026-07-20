# chat-web UI/UX 现状调研(2026-07-20,只读)

> 保留现有青/紫玻璃拟态深色系,不引入新色。全部改法基于既有 token
> (--accent/--violet/--amber/--rose/--radius/--ease-out/.skeleton/.empty-illust/.toast)。
> 关键发现:common.css P4 已备好 `.skeleton/.skeleton-text/.skeleton-card` 等基础设施,
> 但全库 **0 处引用**——多数加载态改法只是"把已有 token 用起来"。

## 可见 bug(Tier 0)

- **T0-W1** `devices.html:18,48` + `handwriting.html:32-33` — `var(--accent-2)` **未定义**,
  渐变声明整条失效:"+ 添加设备"按钮无背景、任务进度条无填充、手写模式切换选中态无底色。
  改:`var(--accent-2)` → `var(--violet)`。
- **T0-W2** `voice-call.html:154` — `.btn-call.active` 用 `var(--violet)` 但本页独立 :root 未定义,
  通话中主按钮背景消失。改:本页 :root 补 `--violet:#8b5cf6`。
- **T0-W3** `devices.html:61 / handwriting.html:52 / usage.html:44` — ≤768px 三页复用 .sidebar
  被 translateX(-100%) 移出屏,但页内**无 menu-toggle**——移动端导航死路。
  改:三页加与 index 相同的 `.menu-toggle` + `.sidebar-overlay` + toggleSidebar()。
- **T0-W4** `playground.css:317-325` — ≤900px 单列布局 .playground-panel{min-height:0} +
  编辑器 absolute 定位 → **Monaco 高度塌缩为 0**,手机看不到编辑器。
  改:`@media(max-width:900px){ .playground-editor-wrap{min-height:240px} .playground-panel{min-height:auto} }`。

## index.html(聊天主页)

- 高 W5 `chat.css:508`+`index.html:286-300`:input-field padding-right 4rem 不够,文字滑入按钮下;
  移动端 pill 图标化 + padding 调整。
- 高 W6 `chat-ui.js:45-50,171-180`:流式中按 Enter 走 abort 分支,**静默取消当前回答且新消息不发**。
  改:`handleKey` 加 `if (isStreaming) return;`,中止只留点按钮。
- 高 W7 `chat.css:593-602`+`chat-ui.js:165-169`:生成中发送按钮只有 spinner,看不出"可点停止"。
  改:loading 态叠方形停止图标(9×9 圆角方块白色),hover 罩 rgba(244,63,94,.18)。
- 高 W8 `chat-messages.js:164-186`:每 chunk 强制滚底,上滚阅读被拽回。
  改:距底 <80px 才自动滚;否则显示"↓ 回到最新"浮动 pill(复用 .input-pill,sticky bottom:8px)。
- 高 W9 `chat.css:763-790`+`index.html:205-227`:375px topbar 溢出。
  改:≤640px 隐藏 #topbarBadge 与"官网",标题 max-width:96px ellipsis。
- 中 W10 `chat-api.js:144-162`:首 token 前空气泡。改:气泡内 3 行 .skeleton-text,首 delta 替换;
  流式尾部加闪烁光标 ▍(fadePulse keyframes 已有)。
- 中 W11 `chat-api.js:199-205`:失败双重提示且不可重试。改:错误气泡内加"重试"按钮(重发最后 user 文本);
  网络错误与 HTTP 错误分文案。
- 中 W12 `chat-messages.js:273-286`:无会话空态悬空。改:插"暂无历史会话"占位或隐藏 section-label。
- 中 W13 `index.html:25`:.history-delete 仅 20×20px。改:28×28+负 margin,桌面 hover 显示,
  触屏(pointer:coarse)常显。
- 中 W14 `chat-ui.js:143-153`:按住说话 <500ms 取消会清空用户草稿。改:按下时快照,取消恢复快照。
- 中 W15 `index.html:326-356`+`chat-ui.js:244-266`:两个 modal 无 Esc/焦点圈定/aria(playground 已做)。
  改:对齐 playground 写法。
- 中 W16 `index.html:66-121`:三张硬编码演示设备卡与真实设备并列误导。改:改名"能力入口"去 status-dot。
- 中 W17 `js/sidebar-devices.js:36-45`:侧栏设备加载空白/失败不可重试。改:2 张 .skeleton-card;失败卡可点重试。
- 中 W18 `index.html:242-261`:.qa-card/.device-card 不可键盘操作。改:role="button" tabindex="0" + Enter/Space。
- 低:W19 topbar"在线"徽章硬编码(online/offline 事件切换);W20 历史消息时间用渲染时刻(存 ts);
  W21 lightbox 无 Esc/关闭按钮。

## devices.html

- 高 W22 `js/devices.js:80-89`:首载网格空白、失败只 toast 无重试。改:3 张 .skeleton-card;
  catch 渲染 .empty-illust + "重新加载"。
- 高 W23 `js/devices.js:376-391,418-429,436`:绑定/解绑按钮无禁用无 loading,连点重复 POST。
  改:进入 disabled+文案"绑定中…",finally 恢复。
- 高 W24 `devices.html:35`:抽屉背景近全透明叠影。改:rgba(20,20,28,.96)+backdrop-filter(与 .modal 一致)。
- 中 W25 `devices.html:113-115`:绑定弹窗输入无 label。改:label 结构或 aria-label。
- 中 W26 `devices.html:91-94`:空态让用户"点右上角"却不给按钮。改:空态内直接放 openBindModal 主按钮。
- 低 W27 `pages.css:15-19`:.busy border-image 不吃圆角。改:inset box-shadow 或 mask 伪元素方案(auth.css:128-148 可复制)。

## handwriting.html

- 中 W28 `handwriting.html:137-138`+`js/handwriting.js:55-58`:生成中仅底部小字。改:spinner 进按钮 +
  result 区盖 .skeleton(min-height:120px)。
- 中 W29 `js/handwriting.js:89-110,181-189`:无设备时提交仍可点。改:禁用 + "去绑定"链接 hint。
- 中 W30 `js/handwriting.js:209-211`:失败清空结果无重试。改:错误块加"重试",保留上次成功预览。
- 低 W31 超字数只计数变红(同步禁用提交);W32 滑块 aria。

## login/register

- 中 W33 密码框无显示/隐藏切换(复用 pages.css .key-toggle-vis)。
- 中 W34 `#turnstile-widget` 无 min-height,渲染时卡片跳动。改:auth.css 补 min-height:65px。
- 低:W35 .auth-error shake 只播一次(remove/void offsetWidth/add);W36 确认密码实时校验;
  W37 登录中按钮加 spinner。

## playground.html

- 中 W38 `playground.html:59,143`:API Key type="text" 明文。改:password + 眼睛切换。
- 中 W39 `js/playground-ui.js:77-89`:历史无删除/清空。改:header"清空"+条目 hover ×。
- 低:W40 resetResponse 空帧占位;W41 空态加 .empty-illust 小图标。

## voice-call.html

- 中 W42 连接中按钮无视觉变化(fadePulse+opacity .7);W43 错误远离按钮且无重试指引(status 加 .error 类+文案);
  W44 未通话时"结束通话"常显可点(默认 hidden/disabled);W45 无返回入口 + 按钮 aria-label;
  W46 通话中模式 select 应禁用。
- 低 W47 本页色板与全站漂移(有意 iOS 风,--accent 系至少对齐)。

## 404 / usage / 跨页

- 低 W48 404.html 圆角/按钮/背景对齐全站。
- 中 W49 `js/usage.js:120-141`:空/错时三张空图表仍占屏;加载中 summary 无 skeleton。
- 中 W50 devices/handwriting/usage 三页页内 style 重复定义 .btn-primary 等(--accent-2 坏 token 温床)。
  改:公共类下沉 pages.css 单一来源。
- 低 W51 .toast 双定义(chat.css:667 vs auth.css:283)合并到 common.css。

## 最高价值 Top10(原文)

1. 修 --accent-2 未定义(T0-W1) 2. 修 voice-call --violet(T0-W2) 3. 三页移动端 menu-toggle(T0-W3)
4. playground 编辑器塌缩(T0-W4) 5. 输入框文字遮挡(W5) 6. Enter 流式误取消(W6)
7. 异步按钮防重复+loading(W23/W28) 8. 流式三件套(W8/W10) 9. 设备页 skeleton+重试(W22)
10. 停止生成可见 affordance(W7)
