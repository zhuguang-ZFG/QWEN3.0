# PRD — 全项目审查第二轮修复(2026-07-20)

## 背景

`docs/reviews/2026-07-20-full-project-review-round2.md`:六路深度审查 + 主线程复现,
产出 10 Blocker(含 5 项物理安全)+ ~25 Warning。本任务批量修复软件侧可修项。
**需硬件在环(HIL)才能验证的固件项**并入活动任务 `07-20-u8-wdt-panic-hil`,本任务不重复。

## 修复清单(验收 = 每项修复 + 门禁通过 + 尽量附回归测试)

### 域 A — 固件安全链路(esp32S_XYZ,最高优先·物理安全)

- [x] A1(FW-F1)STOP/ESTOP 急停:U8 侧改为发合法实时字符(STOP→`!`/FeedHold,
      ESTOP→`0x18`/Reset),或 U1 增自定义实时字节;急停回执改为等 U1 状态确认再报 ok。
      **代码侧修改 + 编译通过;"运动中急停"实机验证并入 WDT 任务 HIL。**
- [x] A2(FW-F3)msg_id 类型:U8 `u1_protocol_client.cc:101` 改发字符串 msg_id;
      加跨端契约测试(schema 要求 string)。
- [x] A3(FW-F9)`application.cc:545` tts 分支 `state->valuestring` 加判空,防远程 crash。
- [x] A4(FW-F10)ota.cc 三处 `CreateHttp(0)` 改为有限超时;CheckVersion ReadAll 加字节上限。
- [x] A5(FW-F11)`Ota::ParseVersion` std::stoi 包 try/catch,防版本号非数字段 panic 循环。
- [x] A6(FW-F6)MCP `self.motor.move_abs` 改为无 z 不下发(对齐 motion_task 的 optional 语义)。
- [x] A7(FW-F12)MotionEventEmitter `last_motion_*` 跨线程访问加锁。
- **A-defer(仅代码不足以闭环,标注并入 HIL 任务)**:FW-F2(UART 引脚)、FW-F4(读放大/主循环阻塞)、
  FW-F5(接收线程同步执行)、FW-F7(HOME 超时)——这些需实机确认或涉及执行架构,记录到 WDT 任务。

### 域 B — 后端越界校验与队列语义(物理安全)

- [x] B1(GW-B1)路径生成类能力(write_text/draw/handwriting)统一过工作区归一化,
      用 resolved profile 的 workspace,取消"生成端自觉"。
- [x] B2(GW-B2)`_normalize_path_to_workspace` 退化跨度按轴独立取 min scale,平移后逐点断言越界拒绝。
- [x] B3(CORE-O4)`dlc_core/path_validator` + schema:bounds 三值 `math.isfinite and >0` 校验,
      拒 NaN/Inf 工作区。
- [x] B4(GW-WA/WB)coordinator draw_svg / restart 排队任务:走正规校验管线或用白名单内 capability,
      且 SEC-06 丢弃时同步置任务 failed(不再幽灵占用 + 假成功)。
- [x] B5(GW-WC)重派发陈旧 ack:引入 dispatch generation/token,ack 携带 gen 比对(替代单布尔时间戳)。
- [x] B6(GW-WD/CORE-O3)async 路径同步 IO 全部包 `asyncio.to_thread`(DNS、SQLite、Redis、simulate、device_status)。
- [x] B7(GW-WG)queued 幽灵老化回收(双后端 max-age)。**部分**:"控制类能力绕过 busy 检查"
      未做——busy 预检在 `dlc_core/dispatch.py`(域 C 边界)且当前 MCP dispatch 不含 estop,实害有限,
      记入遗留(下轮或 HIL 衔接)。

### 域 C — 后端核心/路由/MCP

- [x] C1(CORE-O1)MCP 幂等 duplicate 状态友好处理(不报 -32603;返回幂等成功或提示)。
- [x] C2(CORE-O2)mcp_pipe 子进程非正常退出走退避分支(检查 returncode)。
- [x] C3(CORE-O5)dlc_mcp tools/call 放线程或压 httpx 超时到 ping 窗口内,主循环保持应答 ping。
- [x] C4(RT-W1/W2)`execute_task_template`、`batch_draw` 补 `check_key_limit`;batch svg 加长度上限。
- [x] C5(GW-WH)语音层"急停/estop"直达模式(最高优先级);低置信 fallback 不生成运动任务。
- [x] C6(CORE-Y1)畸形 JSON 不静默丢弃:log.warning + 尽力回 -32700。

### 域 D — chat-web 前端

- [x] D1(FE-1)删 chat-api.js 顶层 `var escapeAttr`/`var isAllowedImageUrl` 别名(改引用全局或 window.LiMaUtils);
      `node --check` + 构建产物验证。**已复现,发布阻断。**
- [x] D2(FE-2)voice-call.html CSP `script-src`/`worker-src` 加 `blob:`(或 worklet 抽同源文件)。
- [x] D3(FE-3)login/register Turnstile 用官方 `?onload=` 显式回调,消除加载竞态。
- [x] D4(FE-4)voice-call 连击守卫(connecting 标志 + 禁按钮;endCall 先剥离旧 ws 事件处理器)。
- [x] D5(FE-5)devices.js 抽屉/轮询代际校验(selectedDeviceId 判废、updateTaskItem 元素缺失时终止轮询、connectStatusWs epoch)。
- [x] D6(FE-6)统一 401 处理:LiMaAPI 抛带 status 错误 → removeToken + 跳 login;控制台加登出入口。

### 域 E — 小程序 manager-mobile

- [x] E1(MP-1)HTTP 层非 200 分支先解析响应体 `{code,message}` 再抛;决定 E_ 码映射补后端或删前端。
- [x] E2(MP-2)WS 补 `task_failed` 事件处理(ServerWsEvent 类型 + switch 分支),失败清 busy/loading。
- [x] E3(MP-3)snapshot/applyRuntimeStatus working=false 时置 idle(用 mapServerEvent 已算好的 phase)。
- [x] E4(MP-4)语音流 touchend 置 stopRequested,startRecording 连接完成后检查并中止;onTouchStart 加 try/catch。
- [x] E5(MP-5)WS 切设备/重连旧 socket 回调 epoch 判废。
- [x] E6(MP-6)配网页 prop 名统一(`isConnectedToESP32`),消除 vue-tsc TS2345。

### 不修 / 降级(记录原因)

- 大量 🟡 Suggestion(死代码清理、i18n 补 key、硬编码中文、CSP 收紧 ws:、fetch 超时等):
  低风险,不阻断,留日常迭代;本任务只做上面列出的 Blocker + 高价值 Warning。
- 固件 A-defer 四项:需 HIL 或执行架构改造,并入 `07-20-u8-wdt-panic-hil`。

## 硬门禁

- 后端:`ruff check` 全绿;`pytest tests/` 不回退(基线 1869 passed / 0 failed),新增修复尽量附回归测试。
- 固件:`idf.py build` 通过(U8);schema 校验通过;不碰上游非点名文件(边界铁律)。
- 前端:改动的 .js `node --check` 通过;构建产物一致。
- 小程序:`npx vue-tsc --noEmit` 不新增错误(修掉 TS2345)。
- 单文件 ≤300 行、单函数 ≤50 行。

## 验收

各域修复完成 + 对应门禁通过 + trellis-check 复核 PASS。固件 A1/A2 的实机验证并入 WDT 任务,
本任务在代码侧 + 编译/静态门禁通过即可收尾。
