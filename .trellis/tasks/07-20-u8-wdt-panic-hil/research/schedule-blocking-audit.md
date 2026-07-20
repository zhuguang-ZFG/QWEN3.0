# Step 1 审计:主循环阻塞路径清单(2026-07-20)

> **⚠️ 修正(2026-07-20 全项目深度审查第 6 路发现)**:本审计"U1 UART 命令默认 120ms
> 超时,安全"的结论**错误**。漏掉了:①`motion_executor.cc:443-445` PATH_END 等待
> 超时 120000ms;②`ReadU1Response`(u1_protocol_client.cc:41-65)每次调用实际消耗
> ≈3×timeout(uart_read_bytes 凑不满 128 字节等满超时 + 2 轮 idle)→ PATH_END 实际
> 阻塞 240–360s,每个 PATH_SEG ≈2.4s(13 段即超 30s)。而 MCP 工具体统一 Schedule
> 到主循环执行 → **run_path / plotter 类语音绘图必然触发 30s WDT panic 重启,且
> U8 重启后 U1 继续无人监管地画**。"最坏有界阻塞 ~15s → 30s 超时"的结论对这些
> 能力不成立。WDT 任务在 HIL 前必须先解决:读放大消除(按行读)+ 长运动任务移出
> 主循环(或分段喂狗),否则 AC2/AC3 无法通过。详见全项目审查报告(固件 F4/F5)。

主循环任务(WDT 注册)执行的代码 = 主循环事件处理 + 全部 `Schedule()` 回调 +
全部 MCP 工具体(`mcp_server.cc:560` 统一 Schedule 到主循环)。
逐一核对 33 个 `Schedule(` 调用点 + 主循环事件分支,按最坏阻塞时长分类:

## 无界阻塞(必须 delete/add)

| 路径 | 最坏时长 | 处置 |
|------|---------|------|
| `mcp_server.cc:161` → `UpgradeFirmware`(`application.cc:1041`)→ `Ota::Upgrade` | 数分钟(下载+写 flash) | **D2 方案 A**:进入时 `esp_task_wdt_delete`,失败分支恢复 `add`。注意该函数也被 ActivationTask(未注册 WDT)调用,需 `esp_task_wdt_status(NULL)==ESP_OK` 判断后再 delete/恢复 |

## 有界长阻塞(5–20s,决定超时值)

| 路径 | 最坏时长 | 依据 |
|------|---------|------|
| MCP 板级工具中的 DLC API HTTP(`motion_executor` FetchWorkspaceMm、board.cc DLC 调用) | ~15s/次 | `CreateHttp(15)` 超时 15s(安全红线"超时禁 0") |
| `ContinueOpenAudioChannel` / WS 开通道(`application.cc:777/826/870`) | TLS 建连 + server hello 等待 10s | `websocket_protocol.cc:229` `pdMS_TO_TICKS(10000)` |
| `Alert` + `vTaskDelay(3000)` 序列(升级前奏、错误提示) | 3–7s | 代码内固定延时 |
| `mcp_server.cc:142` reboot 工具 | ~2s 后重启 | delay(1000)+Reboot 内 delay(1000),随后 esp_restart,无需处理 |

**结论:最坏单次有界阻塞 ≈ 15s(HTTP),叠加序列(hello 10s + 提示延时)可近 15s。
10s 超时必误杀 → `CONFIG_ESP_TASK_WDT_TIMEOUT_S` 提为 30s(≈2 倍最坏有界阻塞)。**
30s 对"自愈重启"目的完全够用,且 6 个音频/LED 任务 5s 心跳余量从 2 倍升到 6 倍。

## 快速路径(<1s,共 20+ 处,抽样确认)

显示更新(SetChatMessage/SetEmotion/ShowNotification)、状态迁移(SetDeviceState)、
PlaySound、SendMcpMessage/SendMotionEvent(入队)、CloseAudioChannel、AbortSpeaking、
EnableDeviceAec、modem Stop、MQTT 重连触发。均远小于 30s,无需处理。

## 排除项

- `sleep_timer.cc:88` 浅睡眠循环跑在主循环上,理论上是无界阻塞;
  但本板(`dlc-motor-control-p1-ai`)未使用 SleepTimer(板目录无引用),不处理,留此记录。
- U1 UART 命令默认 120ms 超时(`u1_protocol_client.h:63`),安全。
- 自动 OTA(`CheckNewVersion`,application.cc:447)跑在 ActivationTask,未注册 WDT,不受影响。

## 对 design.md 的修订建议(已回写)

1. D3:超时 10s → **30s**,心跳维持 5s;无需在 6 个任务里加打点代码——HIL 用
   "PANIC 关 + 低超时(8s)调试 build" 观察 task_wdt 告警即可定位慢循环,零代码侵入。
2. 死锁注入挂钩放**板目录**(自定义区,不碰上游):config.h 加默认关闭的
   `DLC_WDT_TEST_HOOK` 宏,board .cc 的 `InitializeTools()` 里条件注册
   `self.debug.wdt_hang` 工具(工具体 `vTaskDelay(portMAX_DELAY)`,经 mcp_server
   Schedule 恰好挂死主循环,正是要测的路径)。
