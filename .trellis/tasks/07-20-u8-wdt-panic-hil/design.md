# Design — u8 固件 WDT:PANIC 开关与心跳间隔

## 现状(2026-07-20,子模块 500e9c6)

| 项 | 现值 | 位置 |
|----|------|------|
| WDT 超时 | 10s | `sdkconfig.defaults:27` `CONFIG_ESP_TASK_WDT_TIMEOUT_S=10` |
| PANIC 开关 | **未开**(超时仅告警) | `sdkconfig:1827` |
| 注册任务 | 主循环 + AudioInput/AudioOutput/OpusCodec/AudioProcessor/AudioDetection/LED EventTask | application.cc:189, audio_service.cc:239/306/352, afe_audio_processor.cc:143, afe_wake_word.cc:144, gpio_led.cc:262 |
| 心跳 | 统一 5s 有限等待 + 循环头 `esp_task_wdt_reset()` | 同上各文件 |
| Idle 任务 | CPU0/CPU1 均纳入 WDT | `sdkconfig:1829-1830` |

## 决策点 D1:PANIC 开关

推荐:**启用 `CONFIG_ESP_TASK_WDT_PANIC=y`**(写入 `sdkconfig.defaults`),理由:

- 不开 PANIC 时 H2 注册毫无自愈价值:假死设备只多了几行看不到的串口日志(现场无串口)。
- 设备是玩具/绘图终端,重启恢复成本低(秒级),假死需人工断电,重启是更好的失败模式。
- panic 后默认走 `esp_restart`,并可在启动日志读取 `esp_reset_reason()==ESP_RST_TASK_WDT` 作为证据。

备选(若 HIL 发现无法消除的误杀):保持告警模式,主循环增加软件自检
(检测子任务心跳超时后主动 `esp_restart`)。此备选实现成本更高,仅作退路。

## 决策点 D2:OTA 路径防误杀(启 PANIC 的前提)

三个候选,推荐 **方案 A**:

- **A. 升级期间退出 WDT(推荐)**:`UpgradeFirmware` 进入时 `esp_task_wdt_delete(NULL)`,
  失败分支恢复 `esp_task_wdt_add(NULL)`(成功分支直接重启,无需恢复)。
  改动 ≤10 行,语义直白:"升级中我自愿放弃看护"。升级本身挂死的兜底由
  OTA 状态机(pending install + `MarkCurrentVersionValid`)与人工重试承担。
- B. 升级移到独立任务:改动大(Schedule 语义、状态机、栈大小),收益与 A 相同,不选。
- C. `Ota::Upgrade` 进度回调里喂狗:喂狗点依赖 HTTP 分块节奏,慢网/大文件下仍可能 >10s,
  不可靠,不选。

同类排查结论见 `research/schedule-blocking-audit.md`(2026-07-20 完成):
唯一无界阻塞就是 OTA;有界长阻塞最坏 ~15s(板级工具 DLC API HTTP 超时)、
WS 开通道 hello 等待 10s——由 D3 的超时提档吸收,不逐点 delete/add。

## 决策点 D3:心跳间隔与超时(按 Step 1 审计修订)

心跳维持 5s;**超时 10s → 30s**(`CONFIG_ESP_TASK_WDT_TIMEOUT_S=30`)。
依据:主循环最坏**有界**阻塞 ≈ 15s(HTTP 15s 超时、WS hello 10s + TLS),
10s 必误杀;30s ≈ 2 倍最坏有界阻塞,自愈延迟 30s 可接受,
音频/LED 任务 5s 心跳余量升至 6 倍。

不在 6 个任务循环里加打点代码(零上游侵入):HIL 阶段用
"PANIC 关 + `TIMEOUT_S=8` 调试 build" 跑压力场景,凭 task_wdt 告警定位慢循环;
正式配置下 30 分钟压力无告警即判定通过(AC3)。

## 兼容性 / 回滚

- 变更集中在 `sdkconfig.defaults` + 少量 C++;按 board 的 `sdkconfig.defaults.*` 不动。
- 回滚 = revert 子模块一个 commit(PANIC 回到告警模式),无数据迁移。
- 风险窗口:若 D2 排查有漏网长阻塞路径,启 PANIC 后表现为"偶发重启",
  启动日志 `ESP_RST_TASK_WDT` + 前次 panic 回溯可定位,不会静默。

## 验证设计(HIL)

1. **死锁注入**:板目录(自定义区)加默认关闭的 `DLC_WDT_TEST_HOOK` 宏
   (`config.h`),`InitializeTools()` 条件注册 `self.debug.wdt_hang` MCP 工具,
   工具体 `vTaskDelay(portMAX_DELAY)`——经 mcp_server 的 Schedule 恰好挂死主循环。
   观察 30s 后 panic 重启、reset reason 为 `ESP_RST_TASK_WDT`、重启后功能正常。
   挂钩默认不编译进发布固件。
2. **OTA 全流程**:MCP `Schedule` 路径升级真实固件包(>1 分钟下载),无 WDT 触发。
3. **压力**:持续语音对话 + 唤醒 + LED 动效 ≥30 分钟,串口无 task_wdt 告警,
   同时收集 D3 打点数据。
