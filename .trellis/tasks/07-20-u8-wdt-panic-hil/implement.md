# Implement — u8 固件 WDT:PANIC 开关与心跳间隔

> 前置依赖:需要 u8 实机 + 串口 + 可用的 OTA 固件包。无硬件时只能完成 Step 1–3(代码侧),
> Step 4–6(HIL)必须在设备到位后执行,任务在此之前不得报完成。

## Step 1 — 代码侧排查(无硬件)

- [x] grep 主循环 `Schedule(` 全部调用点,列出潜在 >5s 阻塞路径清单,逐一标注
      (安全 / 需 delete-add / 需改造),结论存 `research/schedule-blocking-audit.md`。
- [x] 确认各 board 变体 `sdkconfig.defaults.*` 无 WDT 覆盖项冲突
      (`.esp32` 变体含 TIMEOUT_S=20,但本板锁 esp32s3,其变体无 WDT 项,无冲突)。

## Step 2 — 代码修改(无硬件)

- [x] `sdkconfig.defaults`:加 `CONFIG_ESP_TASK_WDT_PANIC=y`(D1),
      `CONFIG_ESP_TASK_WDT_TIMEOUT_S` 10 → 30(D3,依据 Step 1 审计)。
- [x] `application.cc UpgradeFirmware`:状态守卫通过后
      `if (esp_task_wdt_status(NULL)==ESP_OK)` 则 `esp_task_wdt_delete(NULL)`,
      失败分支按记录恢复 `esp_task_wdt_add(NULL)`(D2 方案 A;
      该函数也被未注册 WDT 的 ActivationTask 调用,必须条件判断);更新函数头注释。
- [x] 修正硬编码超时值的注释:`application.cc:186-188`、`audio_service.cc:7`、
      `afe_wake_word.cc:143`(R4;afe_audio_processor/gpio_led 注释未写死数值,不动)。
- [x] 死锁注入挂钩(板目录,零上游侵入):`config.h` 加默认关闭的
      `DLC_WDT_TEST_HOOK` 宏;board .cc `InitializeTools()` 条件注册
      `self.debug.wdt_hang` 工具(体:`vTaskDelay(portMAX_DELAY)`)。
- [x] ~~D3 循环打点~~ 取消:改为 HIL 低超时调试 build 观察告警(见 design.md D3)。

## Step 3 — 编译门禁(无硬件)

- [x] `idf.py build` 通过(2026-07-20,eim 本地 IDF v5.5.2,set-target esp32s3 + build;
      产物 xiaozhi.bin 2.9MB)。额外发现并修复前置断裂:`b06598f` 的 unique_ptr
      ReturnValue 改造漏改两处裸 `cJSON*` 返回(mcp_server.cc:186、
      u1_protocol_client.cc:374),子模块 commit `0cf91e6`。
- [x] 生成的 `sdkconfig:1827-1828` 确认 `CONFIG_ESP_TASK_WDT_PANIC=y` / `TIMEOUT_S=30`
      (sdkconfig 被 gitignore,不入库)。附加门禁:schema 68/68、GPIO 检查通过;
      pytest 8 failed 全为小程序静态契约测试既有基线(P3.1 组合式重构所致),与本改动无关。
- [x] 子模块 commit:`0cf91e6`(build 修复)+ `87b583d`(WDT 改动),
      分支 `fix/review-2026-07-20-h2-wdt-tasks`。
      **计划修订**:原定"HIL 通过后再 bump 父仓库指针",但父仓库原指针 `500e9c6`
      的子模块状态编译不过(断裂 `0cf91e6` 才修复),钉住不可编译状态更糟——
      故提前 bump 至 `87b583d`(已过编译+静态门禁);HIL 仍是任务完成前提(Step 4-6)。

## Step 4 — HIL:死锁注入(需硬件)【回滚点:revert Step 2 commit】

- [ ] 烧录调试固件,触发死锁挂钩 → 10s 内 panic 重启,`esp_reset_reason()==ESP_RST_TASK_WDT`。
- [ ] 重启后语音/绘图功能正常。串口日志存 `research/hil-deadlock.log`。

## Step 4b — 并入本任务的第二轮审查固件遗留项(需 HIL / 执行架构)

> 来源:`docs/reviews/2026-07-20-full-project-review-round2.md`。这些项 07-20 review-round2
> 任务判定为"仅代码不足以闭环",转入本 HIL 任务处理。

- [ ] FW-F4 run_path/plotter 读放大:`ReadU1Response` 改按行读(读到 `\n` 即返)消除 3× 超时放大;
      PATH_END 阻塞从 240–360s 降到实际用时。这是 30s WDT panic 的直接诱因,HIL 前必做。
- [ ] FW-F5 长运动任务移出主循环 / 接收线程(独立 motion 任务),stop/estop 短路优先。
- [ ] FW-F2 U1 UART0 引脚实机确认:`Serial.cpp:110 setPins(1,3)` 与硬件文档 tx=IO10/rx=IO11
      是否一致;GPIO3 与 X_DIRECTION_PIN 是否双占用。实测链路通不通。
- [ ] FW-F7 HOME 超时:U1 同步 `$H` 完成才回帧,U8 只等 ~750ms 恒报 timeout;
      U1 改先 ack 后异步 result,或 U8 超时提到 30s+ 轮询状态。
- [ ] **A1 phase 契约缺口**(第二轮域 A 复核遗留):STOP/ESTOP 的 motion_event 当前仍报
      `phase:"done"`(`dlc_motor_control_p1_ai_board.cc:550-563`),而回执体已改诚实(signal_sent)。
      需 HIL 加 U1 状态帧确认后再发终态事件:done=确认停车、failed=超时未确认;
      或跨 edge_b/edge_c schema + 网关联合扩展 phase 枚举加 `signal_sent`。
      **在此之前云端不得把 stop 任务的 done 当作"已停机"消费。**
- [ ] B5 衔接:固件 motion_event 回带 `dispatch_gen` 字段(后端已就位,当前不带走旧防重放语义);
      回带后服务端 dispatch generation 防重放才严格生效。

## Step 5 — HIL:OTA 与压力(需硬件)

- [ ] MCP 路径 OTA 真实固件包全流程成功,无 WDT 触发(AC2),日志存档。
- [ ] ≥30 分钟语音+唤醒+LED 压力,无 task_wdt 告警(AC3);收集 D3 最坏耗时数据,
      按判定规则(<5s 维持;否则调 TIMEOUT_S)定稿并记录。

## Step 6 — 收尾

- [ ] 关闭/剥离调试挂钩后出正式 build,复验编译门禁。
- [ ] 决策与数据写入 `.trellis/spec/esp32S_XYZ/`(AC5),更新固件 docs;
      并修正 spec `backend/u8-xiaozhi.md` 红线行"超时禁 0":CreateHttp 参数是模组连接ID非超时,
      应表述为 `SetTimeout(ms)` per-operation(第二轮 A4 复核发现)。
- [ ] bump 父仓库子模块指针,常规提交流程(Phase 3.4),归档任务。

## 验证命令速查

```bash
# 生成配置核对
grep TASK_WDT esp32S_XYZ/firmware/u8-xiaozhi/sdkconfig
# 主循环 Schedule 调用点清单
git -C esp32S_XYZ grep -n "Schedule(" -- firmware/u8-xiaozhi/main
```
