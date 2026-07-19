# PRD — u8 固件 WDT 设计:PANIC 开关与心跳间隔(硬件在环验证)

## 背景

2026-07-20 全量审查遗留项(前置任务 `archive/2026-07/07-20-full-review-fixes` 明确排除范围)。
H2 修复(esp32S_XYZ 子模块 `500e9c6`)已把主循环 + 6 个长运行任务注册到任务看门狗,
但 **WDT 超时目前只打印警告、不会重启设备**:

- `firmware/u8-xiaozhi/sdkconfig:1827` — `CONFIG_ESP_TASK_WDT_PANIC is not set`
- `firmware/u8-xiaozhi/main/application.cc:187` 注释声称"看门狗触发系统重启",与实际配置**不符**
- 结论:任务卡死时设备依旧假死,H2 修复只提供了日志证据,未实现自愈

同时心跳设计未经实机验证:所有注册任务统一 5s 心跳 / 10s 超时(2 倍余量),
音频任务循环内的阻塞调用(I2S 读写、AFE fetch、Opus 编解码)最坏耗时未测量。

## 核心风险(为什么不能直接开 PANIC)

MCP 工具触发的固件升级路径 `mcp_server.cc:161` → `app.Schedule(...)` →
**在 WDT 已注册的主循环任务上**执行 `Application::UpgradeFirmware`(`application.cc:1041`),
`Ota::Upgrade` 下载 + 写 flash 需数分钟且中途不喂狗。
若直接启用 `CONFIG_ESP_TASK_WDT_PANIC=y`,升级进行 10s 后设备被 WDT 重启,
OTA 永远无法完成,且 pending install 状态下可能形成重启循环。
(自动 OTA 路径走 ActivationTask,未注册 WDT,不受影响。)

## 需求

1. **R1 决策并落地 PANIC 行为**:任务挂死时设备应能自愈(重启),而非仅告警。
   前提是消除已知的合法长阻塞路径误杀(至少 R2)。
2. **R2 OTA 升级路径与 WDT 兼容**:主循环执行升级期间不得被 WDT 误杀
   (方案见 design.md:升级前 `esp_task_wdt_delete` / 移出主循环 / 分段喂狗,三选一)。
3. **R3 心跳间隔实机验证**:测量各注册任务最坏循环耗时,确认 5s/10s 组合安全,
   或给出调整后的数值并说明依据。
4. **R4 注释与配置一致**:`application.cc`、`audio_service.cc` 等处关于 WDT 行为的注释
   与最终 sdkconfig 一致,不得再出现"声称重启、实际只告警"的错位。

## 验收标准(需硬件在环)

- [ ] AC1 实机注入主循环死锁(测试挂钩或调试固件),设备在 WDT 超时后按设计行为处理;
      若最终决策为 PANIC=y,则观察到 panic 重启并正常恢复。
- [ ] AC2 实机走 MCP 触发的 OTA 全流程(下载数分钟),升级成功、无 WDT 触发、重启后版本正确。
- [ ] AC3 音频通话/唤醒/LED 常规压力场景连续运行 ≥30 分钟,无 WDT 误报(日志无 task_wdt 警告)。
- [ ] AC4 sdkconfig.defaults 与生成的 sdkconfig 中 WDT 相关项一致提交;代码注释与配置一致。
- [ ] AC5 决策记录(开/不开 PANIC、心跳数值及理由)写入 spec
      (`.trellis/spec/esp32S_XYZ/`)与固件 docs。

## 范围外

- u1-grbl(Grbl_Esp32)的 WDT 策略(独立固件,另议)。
- 中断看门狗(IWDT)与 brownout 配置调整。
- fz-sim 主机仿真只能做冒烟(不能证明真实音频/OTA 时序),HIL 为准。

## 硬门禁

- 固件可编译(idf.py build / example 环境 platformio);
- 单文件 ≤300 行、单函数 ≤50 行(触碰到的文件遵守);
- AC1–AC3 需附实机日志证据(粘贴到任务 research/ 或 journal)。
