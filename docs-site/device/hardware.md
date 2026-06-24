# 硬件参考

LiMa 设备端主要基于 ESP32-S3 与 Grbl 兼容的运动控制器。

## 推荐硬件配置

| 组件 | 推荐型号 | 说明 |
|------|----------|------|
| 主控 | ESP32-S3 | Wi-Fi + 蓝牙，充足算力 |
| 运动控制 | Grbl 1.1f | 开源 CNC 控制器 |
| 步进驱动 | A4988 / TMC2209 | 根据扭矩和静音需求选择 |
| 电机 | 42 步进电机 | 两相四线 |
| 电源 | 12V/5A 或 24V/5A | 根据电机驱动电压 |
| 绘图机构 | CoreXY 或 Cartesian | 根据行程和结构选择 |

## 接线示意

```text
ESP32-S3  ──UART──►  Grbl 控制器  ──STEP/DIR──►  步进驱动  ──►  电机
         ──I2S──►  音频模块（可选）
         ──SPI──►  显示屏（可选）
```

## 传感器与限位

- X/Y 限位开关用于回家定位
- 笔升降舵机或电磁铁控制落笔
- 可选：力传感器、摄像头用于高级功能

## 工作区

Grbl 的 `$130` / `$131` 行程参数必须与机械行程一致。LiMa 下发的路径会在设备端做边界检查，越界任务会返回 `validation failed`。

## 参考文档

- `docs/ESP32S_XYZ_INTEGRATION_GUIDE_CN.md`
- `docs/ESP32S_XYZ_MANAGEMENT_CN.md`
- `docs/ESP32S_XYZ_PROTOCOL_ADAPTER_DESIGN.md`
