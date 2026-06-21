# 固件 v1 → v2 分区表迁移指南

**日期**: 2026-06-22
**适用范围**: `esp32S_XYZ/firmware/u8-xiaozhi`（LiMa 绘图/写字机 ESP32 固件）
**状态**: 运维必读 — v1 存量设备 **不能** 通过 OTA 直接升级到 v2

---

## 背景

u8-xiaozhi 固件从 **v1 分区表** 迁移到 **v2 分区表** 时，Flash 布局发生结构性变化：

| 维度 | v1 | v2 |
|------|----|----|
| 模型/资源 | 固定 `model` 分区（约 960KB） | 可网络更新的 `assets` 分区（SPIFFS） |
| 应用 OTA 槽 | `ota_0` / `ota_1` 各约 6MB（16MB Flash） | 各约 4MB，腾出空间给 assets |
| OTA 兼容性 | — | **与 v1 分区表不兼容** |

v2 分区表详见子模块文档：`esp32S_XYZ/firmware/u8-xiaozhi/partitions/v2/README.md`。

**结论**：已在 v1 分区表上量产的设备，云端 OTA 推送 v2 固件会导致分区偏移错误，升级失败或变砖。**必须 USB 串口全量烧录**（bootloader + 分区表 + 应用 + 初始数据）。

---

## 影响范围

- 出厂或现场烧录时使用 `partitions/v1/*.csv` 的设备
- 移动端/云端已切到 LiMa native API（`/device/v1/app/*`）— **云端功能不受影响**，仅固件升级路径受限
- v2 新产设备（出厂即 v2 分区表）可正常 OTA

---

## 识别方法

1. **构建配置**：检查 `sdkconfig` 或 board README 中 `CONFIG_PARTITION_TABLE_CUSTOM_FILENAME` 是否指向 `partitions/v1/` 或 `partitions/v2/`。
2. **设备上报**：`firmwareVer` / `hardwareVer` 与出厂记录对照；v2 首版固件版本号以 release tag 为准。
3. **Flash 读取**（高级）：串口执行 `esptool.py read_flash 0x8000 0x1000` 解析分区表，确认是否存在 `assets` 分区名。

---

## 迁移步骤（v1 → v2，手动烧录）

### 前置条件

- USB 数据线、已知 COM 口（Windows）或 `/dev/ttyUSB*`
- [esptool.py](https://docs.espressif.com/projects/esptool/) 或 ESP-IDF 环境
- 对应 Flash 容量的 **v2 分区表 CSV**（`partitions/v2/8m.csv`、`16m.csv` 等）
- 完整编译产物：`bootloader.bin`、`partition-table.bin`、`ota_data_initial.bin`、应用 `xiaozhi.bin`（及板级要求的 `srmodels.bin` 等）

### 标准烧录命令（16MB ESP32-S3 示例）

```powershell
esptool.py -p COM3 -b 460800 `
  --before default_reset --after hard_reset --chip esp32s3 `
  write_flash --flash_mode dio --flash_freq 80m --flash_size 16MB `
  0x0      build/bootloader/bootloader.bin `
  0x8000   build/partition_table/partition-table.bin `
  0xd000   build/ota_data_initial.bin `
  0x10000  build/srmodels/srmodels.bin `
  0x100000 build/xiaozhi.bin
```

> 地址与附加 bin 以具体 board README 为准（如 `labplus-ledong-v2`、`sensecap-watcher` 等）。

### 烧录后验证

1. 串口日志：首次启动应触发 assets 下载（若启用网络 assets）。
2. 设备注册：小程序/管理端绑定，`/device/v1/app/devices` 可见 `firmwareVer` 更新。
3. 功能冒烟：`scripts/firmware_hardware_smoke.py` 或板级 `docs/` 中的硬件检查清单。
4. 云端任务：下发 `home` / `calibrate` / `draw_image` 试跑。

---

## 为什么 OTA 不可用？

ESP-IDF OTA 在 **同一分区表** 内切换 `ota_0` ↔ `ota_1`。v1→v2 变更了：

- 分区起始地址与大小
- 分区名称集合（`model` → `assets`）
- 应用槽容量

OTA 包无法携带新分区表；Bootloader 仍按旧表解析，写入 v2 应用会导致地址越界或启动失败。

**LiMa 云端策略**：对已知 v1 设备 **不要** 推送 v2 OTA URL；运维台账标记「需现场烧录」。

---

## 批量迁移建议

| 阶段 | 动作 |
|------|------|
| 台账 | 按 SN / MAC 标记 v1/v2 分区 |
| 备件 | 准备 USB 线、固定 COM 驱动、标准烧录脚本 |
| 现场 | 逐台烧录 + 验证 + 更新台账 |
| 新产 | 出厂统一 v2 分区表，从 v2 起 OTA |

可选：在 `scripts/firmware_hardware_gate.py`（`--flash`）或 `scripts/firmware_hardware_smoke.py` 增加分区版本探测（读取 NVS 或固件 self-check 字段）后再自动化。

---

## 回滚

- v2 烧录失败：重新执行全量烧录（擦除 Flash：`esptool.py erase_flash` 后再 `write_flash`）。
- 需回到 v1：仅当仍保留 v1 完整 bin 与 v1 分区表时，同样 **全量烧录 v1 套件**；不能通过 OTA 回退。

---

## 相关文档

- 子模块：`esp32S_XYZ/firmware/u8-xiaozhi/partitions/v2/README.md`
- 云端设备 API：`docs/xiaozhi_api_openapi.yaml`（`/device/v1/app/*`）
- 部署：`docs/DEPLOY_AND_RELEASE_CONVENTION.md`
