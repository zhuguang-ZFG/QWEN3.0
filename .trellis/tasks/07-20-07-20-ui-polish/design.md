# Design — UI 优化(保留色系,重构布局与交互)

## 并行策略

两域文件树零重叠,两路 trellis-implement 并行:
- 域 W:`chat-web/`(主仓库)
- 域 M:`esp32S_XYZ/server/.../manager-mobile/src/`(子模块)

## 共享设计模式(两域一致执行)

1. **加载态三板斧**:列表/卡片用既有 `.skeleton-card/.skeleton-text`(两侧全局样式都已备好,零新 CSS);
   按钮内 loading = 禁用 + 文案切换("绑定中…")+ 内嵌 spinner;区域级用覆盖 skeleton。
2. **错误态就近可恢复**:错误渲染在动作发生处(卡内/气泡内/表单下),附"重试"动作;
   网络错误与业务错误分文案;toast 只做补充不做唯一通道。
3. **空态三件套**:图标(语义匹配)+ 主文案 + 直接动作按钮(不叫用户"去点别处")。
4. **敏感操作**:物理动作(回原点/暂停)与所有权变更(转让/接受/撤销)一律二次确认,
   确认文案含目标对象(设备名/手机号)。
5. **防重复提交**:异步入口 guard(状态检查在 handler 第一行,不是只改样式)+ per-key loading。
6. **触控目标**:小程序 ≥88rpx,web 触屏 ≥44px;图标按钮补 aria-label。
7. **不引入新色**:所有颜色引用既有 token;发现硬编码色顺手替换为最近 token(Tier 2)。

## 关键决策

- **D1 小程序详情页折叠(M3)**:用 wd-collapse 而非自研,主题变量已配好;
  默认展开=控制/状态/耗材/画廊,折叠=转让/分享/WSS 日志/danger。风险最低的"重构布局"手段。
- **D2 渐变唯一例外(M8 vs M34)**:登录页保留品牌渐变按钮,device-info-card 渐变改 surface+accent 竖条,
  全 app 渐变只剩登录页一处——符合主题注释"95% 干净深色"。
- **D3 chat-web 公共类下沉(W50)**:.btn-primary/.btn-secondary/.btn-danger/.page-shell 收进 pages.css,
  三页页内 style 只留页面特有;这是 --accent-2 类坏 token 的结构性根治。
- **D4 流式滚动(W8)**:距底 <80px 才 autoscroll;"回到最新"pill 复用 .input-pill 样式 sticky 定位;
  不引入虚拟滚动(过度)。
- **D5 契约测试保护**:小程序静态契约测试断言 vue 文件内字符串
  (tests/ci/test_manager_mobile_*.py,基线已有 8 失败)。实现前先 grep 全部断言串,
  被断言的标识符/文案不改名;改后跑该套件对比,**不得新增失败**(8 个既有基线失败不算)。

## 门禁矩阵

| 域 | 门禁 |
|----|------|
| M | `npx vue-tsc --noEmit` 0 error;`pytest esp32S_XYZ/tests/ci/test_manager_mobile_*` 不新增失败 |
| W | 改动 .js `node --check`;vm 共享上下文按 index.html 顺序 eval 不抛;`node scripts/hash-assets.mjs` 重建 dist |
| 共 | 改动文件内 grep 无新增 `#[0-9a-f]{6}` 硬编码色(白名单:token 定义文件本身) |

## 风险与回滚

- 视觉判断风险:我无渲染反馈 → 交付物含逐页改动摘要,用户逐页看;两域各一个 commit,
  页面级不满意可给出单文件 revert 指令。
- M3 折叠分组改变信息可达性(多一次点击)→ 折叠项仅低频运维,可接受;若用户不满意,
  collapse 默认值一行可改。
- W8 滚动行为改变用户习惯 → 阈值 80px 保守,自动滚仍是默认。
