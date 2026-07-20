# 技术债待办清单(low-priority backlog)

> 归档来源:2026-07-20 两轮全项目深度审查 + UI 调研中判定"记录不修/延后"的低优先项。
> 这些不阻断发布,留日常迭代。按域分组,便于后续挑单立项。
> **不含**:已修项、已立任务项(WDT HIL、UI polish Tier0-1)。

## 后端(round1/round2 审查 Suggestion 级)

- dlc_api/routes.py 绕过 façade;403/200 不一致;GET 写库;声纹 409;transfer 守卫;
  audio_store startswith;dispatch 锁泄漏(round1 记录)。
- CORE-Y2 `production_blocked` 恒 False 死信号(access_guard.py:44-58)——删或恢复真实语义。
- CORE-Y3 ws_ticket.py + authenticate_websocket 现役死代码——删或标注废弃。
- CORE-Y5 rate_limiter Redis 失败永久粘滞无冷却(照 idempotency.py 的 30s 冷却)。
- CORE-Y8 /dlc/tasks/validate 端点无限流。
- CORE-Y9 check_rate_limit 每请求 O(n) 全表扫描(按次数/时间触发清扫)。
- CORE-Y11 fail-closed 依赖 LIMA_RUNTIME_ENV 显式设置——核对 DEPLOY 文档是否强制。
- GW-WD 同类漏网(round2 check 发现,审查未点名):dlc_api/routes.py:60 async 内同步 DNS、
  device_app_gallery.py async 内同步 SQLite、images.py:120 同步 DNS。
- GW-1 move_abs/move_rel 解析后必被拒(CAPABILITY_PATH_MAP 缺,但 SEC-06 白名单含)——语义自相矛盾。
- GW-2 handwriting 安全预检 fail-open(应 fail-closed)。
- GW-4 未知 task_id 的 motion_event 自动建 stub(可伪造幽灵状态)。
- RT-S1 created_at 存储格式(空格分隔)与统计窗口(ISO T/Z)字典序比较边界不一致。
- B7 后半:stop/estop 绕过 dispatch.py busy 预检未实现(当前 MCP dispatch 不含 estop,实害有限)。
- 语音 ticket 双连竞态(30s TTL + 一次性 ticket,已接受风险)。
- device_protocol_registry parse_version 预发布版(v1.0.0-rc1)非数字段按 0 判 compatible。

## 固件(round2 F13-F19,非 HIL 项)

- FW-F8 Edge-D error_code 枚举漂移(U1 发 E003/E004 不在 error.schema.json;E001/E002 同名异义)。
- FW-F13 test_u8_protocol_logic.cpp 测试与产线大小写敏感语义漂移(虚假通过)。
- FW-F14 board.cc cJSON_PrintUnformatted 返回值未判空即用(OOM 时 UB)。
- FW-F15 board.cc 文本长度 >40/>80 按字节计,中文约 13/26 字。
- FW-F16 workspace_mm 用编译期常量非运行期 $130-132(现场改软限位后脱节)。
- FW-F17 本地控制 WS 明文 ws://:8080,token 明文头传输(LAN 抓包可重放)。
- FW-F18 audio_service cv.wait 谓词缺 service_stopped_;SetDecodeSampleRate 未持锁窄窗竞争。
- FW-F19 Z 轴 idle-lock 25ms 断使能(已知设计权衡,建议加"位置可信度"提示)。
- ota.cc/assets.cc/mcp_server.cc 若干 CreateHttp(n) 用默认 30s(有限,非危险,未点名)。
- spec backend/u8-xiaozhi.md 红线行"超时禁 0"表述需更正为 SetTimeout(ms) per-operation(round2 A4 发现)。

## chat-web(UI 调研低优先)

- W19 topbar 在线徽章硬编码(online/offline 事件切换);W20 历史消息时间用渲染时刻(存 ts);
  W21 lightbox 无 Esc/关闭按钮;W27 .busy border-image 不吃圆角;W31/W32 手写超字数/滑块 aria;
  W35 auth-error shake 只播一次;W36 确认密码实时校验;W37 登录按钮 spinner;
  W39 playground 历史删除/清空;W40/W41 playground 空帧占位/空态图标;W47 voice-call 色板漂移;W48 404 对齐。

## 小程序(UI 调研低优先)

- M19 quick-link 触控 76rpx/箭头硬编码;M21 gallery 工具栏按钮 56rpx;M24 health tag 英文枚举;
  M25 share 空态/失败不可区分;M26 voice-stream 错误原文不可重试;M32 容器 padding 不统一;
  M33 无下拉刷新;M37 voiceprint 滑删不可发现;M42 config 假 selector;M43 语言弹窗无选中态;
  M44 settings 行字号不齐;M46 voiceprint add 弹窗无标题/校验远离字段;M47 login 失败页内残留。

## 小程序契约测试基线(需专项处理)

- tests/ci/test_manager_mobile_*.py 有 **8 个既有失败**(P3.1 组合式重构后断言未跟上,如
  defaultWriteTextFontId/E_ 码等)。这是测试断言过时,非功能回归——建议单独立项对齐断言,
  勿与 UI 任务混做(UI 任务只保证不新增失败)。
