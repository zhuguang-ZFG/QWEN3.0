# ESP32 固件编译

LiMa 设备端固件基于 ESP-IDF 构建，主要面向 ESP32-S3 绘图/写字机。

## 前置条件

- ESP-IDF v5.x
- Python 3.10+
- USB 数据线及对应 COM 口驱动

## 获取源码

```bash
git submodule update --init --recursive
cd esp32S_XYZ/firmware/u8-xiaozhi
```

## 配置目标芯片

```bash
idf.py set-target esp32s3
```

## 配置分区表

根据 Flash 容量选择分区表：

```bash
# 16MB Flash 示例
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.esp32s3" reconfigure
```

v1 与 v2 分区表不兼容，详见 [OTA 升级](/device/ota)。

## 编译与烧录

```bash
idf.py build
idf.py -p COM3 flash monitor
```

## 常见参数

| 配置项 | 说明 |
|--------|------|
| `CONFIG_PARTITION_TABLE_CUSTOM_FILENAME` | 分区表路径 |
| `CONFIG_IDF_TARGET` | 目标芯片，如 `esp32s3` |
| `CONFIG_ESPTOOLPY_FLASHSIZE` | Flash 容量 |

## 验证

1. 串口日志正常输出 Wi-Fi 连接信息
2. 设备成功向 `/device/v1/events` 上报 `device_info`
3. 管理后台或 App 能看到设备在线

## 参考

- `docs/ESP32S_XYZ_INTEGRATION_GUIDE_CN.md`
- `docs/FIRMWARE_V1_V2_OTA_MIGRATION_CN.md`
