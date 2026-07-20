# 全项目深度审查报告 — 2026-07-20(第二轮)

> 六路并行逐文件通读(固件/后端 device_gateway/后端 routes+device_logic/后端核心+MCP/chat-web/小程序),
> 主线程对最高危发现逐一复现验证。上一轮(07-20 第一轮)已修的 B1-B3 + W1-W12 不在此列;
> 本轮为新发现 + 对既往修复的正确性复核。
>
> **主线程已复现确认(证据级)**:前端 FE-1、固件 FW-F3/FW-F1、后端 GW-B1、CORE-O4。

## 🔴 Blocker(发布前必修)

### 后端 device_gateway

- **GW-B1 路径生成类能力绕过工作区校验,越界坐标下发**(已复现)
  `path_pipeline.py:129-166`、`path_validator.py:146-158`、`path_data.py:92-107`。
  `render_text_task('HELLO WORLD ABC')` 实测 **max_x=183mm**(66 点),文字链路从不做
  `_normalize_path_to_workspace`,仅被 clamp 到 ±200mm;`validate_capability_params`
  对 write_text/draw/handwriting 传 `profile=None` → 只剩全局 ±500mm 兜底。
  同一坐标 run_path 拦、write_text 放行 → 语音"写长句"命令步进电机运动到 183mm,
  60–100mm 行程机器撞限位/撞架。**物理安全。**
- **GW-B2 `_normalize_path_to_workspace` 退化跨度不缩放**(已复现)
  `path_pipeline.py:163-166`:`span_x<=0 or span_y<=0 → scale=1.0`。
  `render_svg_task('M 0 0 L 400 0')` 实测 x∈[2,197]mm,纯水平/垂直线越界下发。
  应按轴独立取 min scale,平移后逐点断言。

### 后端核心

- **CORE-O4 NaN 工作区整体绕过边界校验**(已复现)
  `dlc_core/path_validator.py:39-41` + `dlc_api/schemas.py`(pydantic v2 默认 allow_inf_nan)。
  实测 `validate_path([{x:999999}], workspace={x:NaN})` → `{ok:True}`;finite 版正确拒绝。
  W2 只修了点坐标 NaN,workspace 上界本身没查 → `/dlc/tasks/validate` 安全端点静默放行。
  应对 bounds 三值 `math.isfinite(v) and v>0`。

### chat-web 前端

- **FE-1 chat-api.js 顶层 `var` 撞 chat-messages.js 顶层 `const` → 主页聊天完全瘫痪**(已复现)
  `chat-api.js:4,13`(`var isAllowedImageUrl`/`var escapeAttr`)vs `chat-messages.js:52,55`
  (`const` 同名)。经典脚本共享全局作用域,index.html 先加载 messages 后加载 api,
  `var` 重声明已存在的全局词法绑定 → **chat-api.js 求值即抛 SyntaxError,一行不执行**;
  `sendMessage`/`generateImage` 全部未定义。vm 双脚本共享上下文已复现 SyntaxError,
  **构建产物 dist/*.js 同样命中**。6892e88d 的 fallback 引入。删掉这两个 var 别名即可。
- **FE-2 voice-call.html CSP 未放行 `blob:` → AudioWorklet 加载被拦,麦克风采集失效**(待实机)
  `voice-call.html:6`(`script-src 'self' 'unsafe-inline'`)vs `:322,392`
  (`audioWorklet.addModule(URL.createObjectURL(blob))`)。两种通话模式都无法上行音频。
  `script-src`/`worker-src` 加 `blob:`,或把 worklet 抽成同源静态文件。

### 固件(U8↔U1 链路三重失效,相互印证)

- **FW-F1 STOP/ESTOP 急停完全无效**(已确认帧格式)
  `u1_protocol_client.cc:163-178` 发裸文本 `"STOP\n"`/`"ESTOP\n"`;U1 `Protocol.cpp:196`
  私有协议只认 `input[0]=='@'` 的 JSON 帧 → 急停当坏 G-code 排队,画完才报错。
  且 PATH_END 执行期间 U1 主循环阻塞,只有实时字符(`!`=FeedHold、`0x18`=Reset)能即时生效。
  `motion_executor.cc:98-114` 还只要 UART 写成功就回 `ok:true` → 云端被告知已停,机器仍动。
  **最需要急停的"绘图中夹手"窗口,当前任何软件急停都到不了执行层。物理安全。**
  修:STOP→`!`、ESTOP→`0x18`(或 U1 增自定义实时字节);急停回执改为等 U1 状态确认。
- **FW-F3 msg_id 类型契约违背 → 所有 capability 响应被判失败**(已确认双端)
  U8 `u1_protocol_client.cc:101` 发**数字** msg_id;`cmd.schema.json:13-15` 要求 string;
  U1 `json_utils.cpp:29-33` 硬要求值以 `"` 开头,数字值解析失败回空串 →
  U8 `ParseCapabilityResponse:398` `strtoul("")=0` ≠ 请求 id → 全判 `msg_id_mismatch`。
  命令实际会执行(MOVE 会动、HOME 会归零)但云端全收"失败"→ 上层重试造成**重复运动**;
  启动自检 `CheckU1Uart` 恒 failed。修:U8 发字符串 msg_id(一行)+ 跨端契约测试。
- **FW-F2 U1 UART0 引脚未按硬件适配 + GPIO3 双占用**(待实机)
  `Serial.cpp:110` `Uart0.setPins(1,3)`(上游默认脚未改),硬件文档要求 tx=IO10/rx=IO11;
  且 GPIO3=X_DIRECTION_PIN。后果:U8→U1.IO11 数据没在收;X_DIR 翻转的 ≥0x80 字节被当
  扩展实时命令执行 → 运动中随机 feed-hold/reset。需实机确认链路,若实测通说明文档与线不符。
- **FW-F4 run_path/plotter 主循环阻塞 ≥240s,必触发 30s WDT panic**(修正了 WDT 任务审计)
  `motion_executor.cc:443` PATH_END 超时 120000ms;`ReadU1Response` 每次 ≈3×timeout
  (uart_read_bytes 凑不满 128 字节等满)→ PATH_END 实际阻塞 240–360s。MCP 工具体 Schedule
  到主循环 → 每次语音画图触发 WDT panic,U8 重启后 U1 继续无人监管画。**已回写 WDT 任务
  的 research/schedule-blocking-audit.md**(原"最坏 15s"结论对这些能力不成立)。
  修:ReadU1Response 改按行读消除 3× 放大 + 长任务移出主循环/分段喂狗。
- **FW-F5 云端 motion_task 在接收线程同步执行 → 运行中任务堵住后续 STOP**
  `application.cc:590` motion_task 直接 `HandleMotionTaskJson`(非 Schedule),run_path 占接收线程
  ≥240s → 后续云端 stop/estop 要等画完才解析。修:接收线程只入队,执行放专职任务,stop 短路。

## 🟠 Warning(重要,尽快)

### 固件
- **FW-F9 `application.cc:545` tts 分支 `state->valuestring` 空指针解引用** → 服务端发不带 state 的
  `{"type":"tts"}` 即崩溃重启(认证通道内远程 crash)。加判空。
- **FW-F10 ota.cc 违反"超时禁 0"红线**:`CreateHttp(0)`(ota.cc:212/526/726)无限阻塞;
  `CheckVersion` ReadAll 无字节上限。半开连接挂死激活/升级。
- **FW-F11 `Ota::ParseVersion` std::stoi 未捕获异常** → 版本号含非数字段(`1.2.0-rc1`)→
  ActivationTask terminate → panic 重启循环。
- **FW-F6 MCP `self.motor.move_abs` 默认下发 z=0** → P1"2D 移动落笔"修复未覆盖 MCP 路径
  (云端 LLM 可见,只给 x/y 时 Z 压 0)。改为无 z 不下发。
- **FW-F7 HOME 超时误报**:U1 同步执行 `$H` 完成才回帧,U8 只等 ≈750ms → 归零成功却恒报 timeout。
- **FW-F12 MotionEventEmitter 跨线程 `last_motion_*` std::string 数据竞争**(协议线程写、主循环读,无锁)。
- **FW-F8 Edge-D error_code 枚举漂移**:U1 发 E003/E004 不在 error.schema.json 枚举;
  且 E001/E002 schema 语义与 Protocol.cpp 用法同名异义。

### chat-web
- **FE-3 login/register Turnstile 加载竞态** → 冷加载时组件不渲染且登录永久卡死(用官方 `?onload=` 回调)。
- **FE-4 voice-call 连击"开始通话"竞态** → 麦克风流泄漏(mic 常亮)+ 孤儿 WS 反杀新通话。
- **FE-5 devices.js 抽屉竞态 + 任务轮询器泄漏**(串台解绑作用于错误设备;关抽屉后每 2s 打 API 直到刷新)。
- **FE-6 全站无 401/登录态过期处理,且无任何登出入口**(token 过期后每 10s 用死 token 轮询;logout 零调用)。

### 小程序
- **MP-1 HTTP 层丢弃所有 4xx 业务错误信息**(`alova.ts:155-159` 从不读响应体)→ 任务被拒只显示
  "请求错误(400):request:ok",后端 sanitize 的 message 全丢;`E_*` 错误码映射全是死代码(后端无此码)。
- **MP-2 WS 漏处理 `task_failed` → 设备永久"忙"**(`useDeviceWebSocket.ts:87`)→ 任务失败后
  isDeviceBusy 恒 true,写字/画图/回原点/自检全被拦,healthCheckLoading 永不复位,只能退出重进。
- **MP-3 snapshot/手动刷新只置 running 从不清回 idle**(`useDeviceEvents.ts:84,215`)→ 加剧 MP-2 锁死。
- **MP-4 语音流"松手后才开录且停不下来"竞态**(`useVoiceStream.ts:84`)→ 麦克风持续录音推流。儿童设备,隐私。
- **MP-5 WS 断连/切设备旧 socket 回调未解绑** → 状态污染 + 重复连接(用 epoch 判废)。
- **MP-6 配网页 prop 名 `isConnectedToEsp32` vs `isConnectedToESP32` 不匹配** → 已连热点仍显示未连
  (vue-tsc 全仓唯一报错 TS2345,真实运行时缺陷)。

### 后端
- **RT-W1 `execute_task_template` 缺限流** → 循环 POST 模板 execute 绕过 dlc_task_per_min 无限入队。
- **RT-W2 `batch_draw` 无限流 + svg 无长度上限**。
- **GW-WA coordinator draw_svg 不在 SEC-06 白名单,Redis 模式静默丢弃却报成功** → 幽灵任务占用设备至 30 天 TTL。
- **GW-WB restart_device 排队任务无 capability,同样被丢弃却回 queued** → 重启永不送达 + 幽灵占用。
- **GW-WC W4 修复残留:重派发后陈旧 ack 被接受**(防重放失效,窗口 [recover, re-dispatch));应引入 dispatch generation。
- **GW-WD 阻塞调用混入 async**(`image_url_validation.py:36` 同步 DNS、`task_draw_params.py:75` 同步 SQLite、
  `task_creation_builders.py:63` 同步 Redis+simulate)——硬门禁违反,包 to_thread。
- **GW-WE pen-up 语义未实现**(文字/SVG 都会画跨字母连笔;path_optimizer compress 还会删掉重复点标记)。
- **GW-WF svg_parser 丢隐式坐标序列 + 相对 `m` 子路径起点重置为(0,0)**(图形失真 + 假笔画)。
- **GW-WG queued 幽灵永久 device_busy 无老化回收**(下发通道已退役,入队任务永停 queued)——待确认执行队列归属。
- **GW-WH 语音层"急停"无模式,未知指令回退成"写字"物理动作**(`intent.py:35`)+ estop 不在 FAMILY_ALLOWLISTS。
- **CORE-O1 MCP 内容寻址幂等键:同一指令 10min 内重复必失败且报 -32603**(用户听到内部错误)。
- **CORE-O2 mcp_pipe 子进程秒挂无退避紧循环重连**(B2 修复暴露:清洁关闭未区分"对端关 WS"与"子进程死")。
- **CORE-O3 device_status.py async 内联同步 Redis 全量 HGETALL**(W10 修复遗留;同库 dispatch.py 已用 to_thread)。
- **CORE-O5 dlc_mcp 单线程阻塞循环,慢工具调用期间不应答 ping 可能被 broker 掐线**(待确认 ping 窗口)。

## 🟡 Suggestion(择机)

后端:CORE-Y1 畸形 JSON 静默丢弃(违硬门禁)、Y2 `production_blocked` 恒 False 死信号、
Y3 ws_ticket.py 死代码、Y5 rate_limiter Redis 失败永久粘滞无冷却、Y8 validate 端点无限流、
Y11 fail-closed 依赖 `LIMA_RUNTIME_ENV` 显式设置(待确认部署强制)、GW-1 move_abs/move_rel 解析后必被拒、
GW-2 handwriting 安全预检 fail-open、GW-4 未知 task_id motion_event 自动建 stub(可伪造幽灵)、
RT-S1 created_at 存储格式与统计窗口比较边界不一致。
前端:FE-7 playground shellQuote `\$` 非法转义、FE-8 formatContent `$` 替换模式碰撞、
FE-9 API Key sessionStorage 键名分裂、FE-10 一批(usage echarts 无守卫、devices CSP 放行任意 ws:、
app-boot WebSocket 包装丢静态常量、asset-upload SVG 黑名单可绕、全站 fetch 无超时)。
小程序:MP-7 耗材状态从不初始加载、MP-8 i18n 缺 key(断网 toast 显示 `common.networkOffline`)、
MP-9 设备列表快捷控制无代码级守卫、MP-10~17(自检 loading 无兜底、device_secret 恒空、
WS 心跳空转、转让/接受无确认、声纹删除失败静默、硬编码中文、~1400 行死代码、上传绕过 401 刷新)。
固件:FW-F13~F19(测试与产线语义漂移、cJSON_Print 返回值未判空、长度按字节计中文、
workspace 编译期常量与运行期 $130 脱节、本地控制 WS 明文、audio cv.wait 谓词缺停止位、Z 轴 idle-lock 权衡)。

## 既往修复复核结论

- 07-20 第一轮 B1(voice-call 括号)/B2(mcp_pipe FIRST_COMPLETED)/B3(deploy .venv)、
  W1/W3/W6/W7/W8/W9/W10/W12 — 复核**均正确**;W2(Z 轴/点 NaN)**只修一半**(workspace NaN 漏 → CORE-O4);
  W4(recovered_at 清除)修了原问题但暴露 GW-WC 重派发窗口;W5(INCR+EXPIRE 原子化)正确完整;
  W10 分层正确但遗留 CORE-O3 事件循环阻塞。
- 今日 WDT 提交 87b583d + build 修复 0cf91e6 — CJsonPtr 包裹复核正确(漏包会编译失败);
  但 FW-F4 表明 WDT 任务的阻塞审计漏了 PATH_END,HIL 前需先解决读放大。
- 根仓库 pytest 基线:**1869 passed, 6 skipped, 0 failed**(健康)。

## 优先级建议(按物理安全 + 阻断性)

1. **FW-F1 急停失效** — 最高,直接关系夹手/撞机安全,HIL 必验"运动中急停"。
2. **GW-B1 + GW-B2 + CORE-O4 越界校验三洞** — 步进电机越界运动,物理安全。
3. **FE-1 主页聊天瘫痪** — 已复现,单点删两行即可,发布阻断。
4. **FW-F3 msg_id 契约** — U8↔U1 全链路"假失败+重复运动",一行修 + 契约测试。
5. **MP-1 + MP-2 + MP-3 小程序失败路径死角** — 任务失败后看不到原因且无法再下发。
6. FW-F4/F5(WDT panic 与急停堵塞)并入 WDT 活动任务一起做 HIL。
