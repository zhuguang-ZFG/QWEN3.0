# manager-mobile 小程序 UI/UX 现状调研(2026-07-20,只读)

> 保留克制青绿深色系(#2dd4a7),不引入新色。路径基于
> `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src/`。
> 关键发现:`style/index.scss` 的 `.skeleton*`、`.pulse-dot`、`.telemetry-row`、`.dark-input`
> 四套工具类**几乎无人使用**;gallery-panel 是交互标杆(skeleton/空态/进度/删除确认俱全),
> 重构其他卡片以它为模板。

## Tier 0 可见违和

- **T0-M1** `pages/device-config/components/wifi-connection-status.vue:58-87` — 深色 app 里的
  **浅色 Bootstrap 配色补丁**(#fff3cd 黄/#d4edda 绿),全项目最刺眼违和点。
  改:警告 `--amber-g`/`--amber`,成功 `--green-g`/`--green`。

## device-detail(11 卡)

- 高 M2 `index.vue:148-160`+`device-info-card.vue:5-11`:infoLoading 是**死 prop**,首屏无 skeleton。
  改:info-card 加 `v-if="infoLoading && !deviceInfo"` 渲染 .skeleton-text;supplies/task-status 套 .skeleton-card。
- 高 M3 `index.vue:170-236`:11 卡等权堆 6+ 屏。改:transfer/share/WSS 日志/danger-zone 收进
  wd-collapse(--wot-collapse-* 已配),默认折叠;或分组小节标题"控制/耗材/高级"。
- 高 M4 `task-status.vue:14-35`:任务反馈中枢却存在感最低,原始英文枚举直出。
  改:空态"暂无进行中任务";running 边框 --accent + .pulse-dot;phase 表驱动本地化;
  failed 卡内显示原因 + 重试按钮。
- 高 M5 `transfer-panel.vue:20-54`:裸 transferId 输入框用户看不懂。改:双态渲染——
  默认只有手机号+发起;deviceTransfer 存在时切状态视图(tag+手机号+取消),transferId 自动带入隐藏。
- 高 M6 `useDeviceTransferAndShare.ts:40-99`:发起/取消/接受转让**均无二次确认**(所有权变更)。
  改:三个 handler 加 message.confirm(含手机号/设备 ID)。
- 高 M7 `share-panel.vue:106-108`:分享 token `@click="()=>{}}"` 空操作,**无法复制,分享事实不可用**。
  改:setClipboardData + toast + copy 图标。
- 中 M8 `device-info-card.vue:54-57`:大面积青→蓝渐变违背克制主题(全页唯一大色块)。
  改:--surface 底 + 左侧 6rpx accent 竖条;状态点复用全局 .pulse-dot(本地 .status-dot 删)。
- 中 M9 `index.vue:252-264` vs 各组件:.bento-card/.bento-title 十份重复定义且不一致
  (字号/700 vs 600/padding/阴影有无)。改:统一提到 style/index.scss,组件删本地;阴影策略二选一。
- 中 M10 `index.vue:176-181`+useDeviceActions(handleHome):"回原点"物理动作无确认。改:message.confirm。
- 中 M11 `index.vue:213-226`:WS 断开只有灰 tag,用户不知道进度停更。改:--amber-g 横幅 + ≥88rpx 重连按钮。
- 中 M12 `supplies-panel.vue:23-45`:纸/笔挤一行主次不分;按钮三语义色堆排。
  改:两行 .telemetry-row;按钮统一 plain,仅主操作 primary;成功 uni.vibrateShort。
- 中 M13 `health-check.vue:64-71`:自检 loading 期间历史区无变化;离线仍可点。
  改:插"自检进行中…"行(wd-loading);:disabled="!deviceOnline" + 说明。
- 中 M14 `gallery-panel.vue:216`:删除仅靠 longpress 零提示。改:选中态角标 44px delete 圆钮(走既有确认)。
- 中 M15 `gallery-panel.vue:206-208`:空画廊一行灰字。改:icon+文案+"上传第一张"按钮。
- 中 M16 `voice-approval.vue:55-78`:原始 JSON/requestId 直出;拒绝无确认;loading 全局单值全员转圈。
  改:解析关键字段、原始收进展开区;拒绝 confirm;per-taskId loading。
- 中 M17 `voice-stream-panel.vue:34-47`:录音中无持续视觉、松手无"识别中"过渡。
  改:recording 换 --danger 底+计时;stop→transcript 间 wd-loading"识别中…"。
- 中 M18 `write-draw-panel.vue:26-48`:busy 用红色(语义过重)。改:--amber + clock 图标;
  按钮 busy 时文案"设备忙碌中"。
- 低:M19 quick-link 触控 76rpx<88 + 箭头 #c7c7cc 硬编码;M20 danger-zone 硬编码 #ef4444(→--danger);
  M21 gallery 工具栏 small 按钮 56rpx;M22 选中描边 rgba(59,130,246)(→--accent-glow);
  M23 transfer/write-draw 输入框硬编码 #14181f(→.dark-input);M24 health tag 枚举英文直出;
  M25 share 空态/加载失败不可区分;M26 voice-stream 错误原文直出不可重试。

## device-list

- 高 M27 `index.vue:141`:首页 loading 孤 spinner。改:2-3 张 .skeleton-card。
- 高 M28 `index.vue:107-126,162-164,223-228`:快捷"暂停"(急停语义)与"接受转让"点击即发**无确认**。
  改:confirm(pause 注明"将暂停当前任务")。
- 中 M29 `index.vue:205-228,400-409`:离线仅 opacity .3 **但 @click 未拦截**仍发请求;
  quickLoading 无 spinner 可连点。改:入口 guard + per-key wd-loading + "离线" label。
  (注:round2 修复 E 域已在功能层加过守卫的部分,以现代码为准复查后再改)
- 中 M30 `index.vue:169-182`:空态铃铛图标语义不符、无副文案。改:换图标 + "先配网,再 SN+绑定码添加"。
- 中 M31 `index.vue:52-53`:列表失败只 toast 无页内重试。改:loadError ref + 错误态块 + 重新加载。
- 低:M32 容器 padding 不统一(对齐 24rpx 20rpx);M33 无下拉刷新(enablePullDownRefresh)。

## login / settings / voiceprint / device-config

- 中 M34 `v2/login/index.vue:81-117`:#07070f/#8b95a8/#5a6372 等漂移硬编码 → token;
  渐变按钮与 M8 二选一保留(建议登录页为唯一例外)。
- 中 M35 `settings/index.vue:99-186`+SectionCard:整页硬编码色脱钩 token;两种危险按钮形态并存。
  改:批量换 var(--*);清缓存改 wd-button type=error plain;危险色统一 --danger。
- 中 M36 `voiceprint/index.vue:129,144-153`:全 app 唯一直角卡 + swipe 直角。
  改:rounded-[24rpx] + 容器 overflow-hidden。
- 中 M37 `voiceprint`:滑删唯一入口不可发现。改:一次性提示或角标入口;FAB 尺寸升默认。
- 中 M38 `wifi-network-list.vue:47-54`:扫描中列表区空白。改:3 条 skeleton 行或居中 loading+文案。
- 中 M39 `wifi-config.vue:63-106`:配网失败只 toast、成功一条超长 toast。
  改:submit 下结果条(成功 --green-g / 失败 --danger-g+重试);成功拆 checklist。
- 中 M40 `wifi-config.vue:134-143`:disabled 不知原因。改:按钮下 --dim 原因文案。
- 低:M41 wifi-selector 触控/箭头硬编码 #9d9ea3;M42 config index 假 selector;
  M43 settings 语言弹窗无选中态;M44 行字号不齐;M45 privacy-permissions 第三种卡片写法(复用 SectionCard);
  M46 voiceprint add 弹窗无标题+校验提示远离字段;M47 login 失败页内残留提示。

## 最高价值 Top10(原文)

1. 浅色补丁(T0-M1) 2. 列表骨架屏(M27) 3. 离线/忙防误发(M29) 4. 敏感操作确认补齐(M28/M6/M10/M23)
5. 详情页折叠分组(M3) 6. 分享 token 可复制(M7) 7. task-status 反馈中枢(M4)
8. transfer 双态重构(M5) 9. bento-card 全局统一(M9) 10. 硬编码色→token 清扫(M34/M35/M20/M22/M23)
