# U1 / MOTOR_MCU 规范（Grbl_Esp32）

> U1 = 纯串口运动 MCU。**唯一自定义代码**是机型文件 `firmware/u1-grbl/Grbl_Esp32/src/Machines/dlc_motor_control_p1.h`（对标 `DLC_Motor_Control_P1_V1.0_260513` PCB）。其余全是上游 Grbl_Esp32。

## 目录结构（非标准，注意 src_dir 改写）

`platformio.ini` 里 `[platformio] src_dir = Grbl_Esp32`，所以源码不在默认 `src/`，而在 `firmware/u1-grbl/Grbl_Esp32/src/`（其内又有一层 `src/`）。机型文件落在 `.../src/Machines/`。

- 机型选择入口：`Grbl_Esp32/src/Machine.h`（默认 `#include` 本项目机型文件，见 `docs/U1-Grbl适配说明.md` §1）。
- 构建目标：`default_envs = release_esp32s3`（`[env]` 段的 `espressif32@3.0.0`/`esp32dev` 只是继承基线，注释明示实际是 S3）。
- 构建宏：`-DDISABLE_BLUETOOTH -DDISABLE_WIFI`（U1 不带无线）。
- `build_src_filter` 显式 `-<src/I2SOut.cpp>`（S3 不用 I2S 步进）。

## 编码风格（`CodingStyle.md` + `.clang-format` 强制）

| 项 | 规则 |
|----|------|
| 格式化 | `.clang-format` 强制：`ColumnLimit: 140`、`IndentWidth: 4`、`AccessModifierOffset: -4`。提交前必须过 clang-format。 |
| 头文件守卫 | 一律 `#pragma once`，不用 `#ifdef` 守卫 |
| 类/命名空间 | `CamelCase`（仅当否则会以数字开头时才前导 `_`，如 `_10V`） |
| 成员函数 | `snake_case` |
| 成员变量 | `_snake_case`（前导下划线） |
| 文件名/目录名 | 文件名=类名，目录名=命名空间；一个文件一个类 |
| `using namespace` | 头文件禁止（函数体内除外）；cpp 内尽量在函数体用 |
| include 顺序 | cpp 先 include 对应 .h；系统/库用 `<...>`，本地用 `"..."`；禁止 include .cpp |
| **机型文件** | **必须用 `// clang-format off` / `// clang-format on` 包裹**（上游约定，`dlc_motor_control_p1.h` 已遵守） |

电机驱动走基类 `src/Motors/Motor.h` + 工厂模式（`src/Motors/Motors.cpp`）：具体驱动如 `StandardStepper`、`TrinamicDriver`、`RcServo`、`Servo`、`UnipolarMotor` 均继承 `Motor` 并在工厂注册。

## 运动能力现状（document reality）

机型文件 `dlc_motor_control_p1.h` 实际落地情况：

| 能力 | 状态 | 关键定义 |
|------|------|---------|
| 步进 XYYZ | 已落地 | X=GPIO46/3, Y=GPIO8/18, Y2=GPIO17/16, Z=GPIO6/5；`N_AXIS=3`，Y2 作 ganged |
| 共享使能 | 已落地 | `STEPPERS_DISABLE_PIN=GPIO_NUM_4`；`DEFAULT_STEPPER_IDLE_LOCK_TIME=25`（单位 ms，见 `Defaults.h` 注释 + `Stepper.cpp` `*1000` 转 μs；停止后约 25ms 释放使能，让 Z 弹簧机构回 pen-up —— **非常使能**，注释见机型文件 L87-88） |
| 原点/限位 | 已落地 | X=GPIO9, Y=GPIO12, Y2=GPIO13, Z=GPIO14；回零顺序 Z→X→Y+Y2；`DEFAULT_HOMING_SQUARED_AXES=bit(Y_AXIS)`、`LIMITS_TWO_SWITCHES_ON_AXES=1`、`HOMING_INIT_LOCK` |
| 激光 | 已落地 | `SPINDLE_TYPE=SpindleType::PWM`、`SPINDLE_OUTPUT_PIN=GPIO45`、`DEFAULT_LASER_MODE=1`（实现：上游 `src/Spindles/Laser.cpp` + `PWMSpindle.cpp`） |
| 舵机 / 抬笔 | **未落地** | 机型文件无 SERVO 定义。架构 v2 §10bis.7 要求 pause/cancel 自动抬笔；`pen_mode` 协议层存在但 U1 侧未实现（上游有 `src/Motors/Servo.cpp`/`RcServo.cpp` 可用） |
| 压力 HX711 | **明确不接入 Grbl** | 机型文件注释："Pressure sensing is done through HX711 and is not wired into Grbl probe logic" —— 走独立通路，非 Grbl 职责 |

写规范时把这些状态当**当前事实**，不要把"未落地"写成"已支持"。

## strapping pin 风险（硬规则）

`GPIO46 / GPIO3 / GPIO45 / GPIO0` 是 ESP32-S3 strapping pins。机型文件每处使用都带 `// ↑ strapping pin — 已知风险` 注释，并由 `tools/check_gpio.py` 静态强检：

- `STRAPPING_PINS = {0, 3, 45, 46}`：当 OUTPUT 必须带「已知风险」标记，否则 `make test-gpio` 报错。
- `UNAVAILABLE_PINS = {35, 36, 37, 41, 42}`：N16R8 模组未引出，禁用。
- 冲突点：GPIO45 同时是 U1 激光输出和 U8 I2S_DOUT（U8 `config.h` 注明"实测无冲突"）。

**规则**：改任何引脚后必须 `make test-gpio` 通过；新用 strapping pin 必须在机型文件加风险注释。

## 安全层不可绕过（架构 v2 §10bis.10）

禁止 `force` / `unsafe` / `skip_check` 类参数覆盖安全裁决。抬笔保护 / `pen_mode` / z 轴 clearance 是 U1 实现义务（当前未落地，见上表，属已知 tech debt）。

## 未来迁移：FluidNC

`docs/U1-FluidNC迁移计划.md`（2026-07-02）计划从 Grbl_Esp32（上游停更，末次提交 2023）迁到 FluidNC（YAML 运行时配置）。**当前在 Grbl 机型层做改动时，避免做 FluidNC 不支持的事**；命名/配置组织预留 YAML 友好结构。已完成 `dlc_motor_control_p1.h` → `.yaml` 字段对照表。

## 代码示例（机型文件片段，逐字取自 `dlc_motor_control_p1.h`）

```cpp
#pragma once
// clang-format off

#define MACHINE_NAME "DLC Motor Control P1 XYYZ"
#define N_AXIS 3

// Home Y/Y2 independently to square the gantry.
#define DEFAULT_HOMING_SQUARED_AXES (bit(Y_AXIS))

// Driver outputs —— X=GPIO46/3, Y=GPIO8/18, Y2=GPIO17/16, Z=GPIO6/5
#define X_STEP_PIN              GPIO_NUM_46
// ↑ strapping pin IO46 — 已知风险：上电时若 IO46=0 可能导致启动异常，实测确认 PCB 无外部下拉
#define X_DIRECTION_PIN         GPIO_NUM_3
// ↑ strapping pin IO3 — 已知风险：JTAG 复用，上电时序依赖内部弱上拉
#define Y_STEP_PIN              GPIO_NUM_8
#define Y_DIRECTION_PIN         GPIO_NUM_18
#define Y2_STEP_PIN             GPIO_NUM_17
#define Y2_DIRECTION_PIN        GPIO_NUM_16
#define Z_STEP_PIN              GPIO_NUM_6
#define Z_DIRECTION_PIN         GPIO_NUM_5

// Shared enable line for all external drivers.
#define STEPPERS_DISABLE_PIN    GPIO_NUM_4

// Independent home / limit inputs.
#define X_LIMIT_PIN             GPIO_NUM_9
#define Y_LIMIT_PIN             GPIO_NUM_12
#define Y2_LIMIT_PIN            GPIO_NUM_13
#define Z_LIMIT_PIN             GPIO_NUM_14
// Optional future probe input is not assigned in this board revision.
// Pressure sensing is done through HX711 and is not wired into Grbl probe logic.

// Laser output through low-side MOSFET.
#define SPINDLE_TYPE            SpindleType::PWM
#define SPINDLE_OUTPUT_PIN      GPIO_NUM_45
// ↑ strapping pin IO45 — 已知风险：VDD_SPI 电压选择，上电电平影响内部 flash 电压

// Release motor enable shortly after motion stops so XY can de-energize and
// the spring-loaded Z mechanism can return to pen-up when the motor is idle.
#define DEFAULT_STEPPER_IDLE_LOCK_TIME    25

// Run Z first, then X, then Y/Y2 together with squaring enabled.
#define DEFAULT_HOMING_CYCLE_0            (bit(Z_AXIS))
#define DEFAULT_HOMING_CYCLE_1            (bit(X_AXIS))
#define DEFAULT_HOMING_CYCLE_2            (bit(Y_AXIS))

#define LIMITS_TWO_SWITCHES_ON_AXES       1
#define DEFAULT_LASER_MODE                1
#define DEFAULT_X_STEPS_PER_MM            80.0
#define DEFAULT_Y_STEPS_PER_MM            80.0
#define DEFAULT_Z_STEPS_PER_MM            400.0
```

要点：引脚一律 `GPIO_NUM_xx`；strapping pin 必带 `↑ strapping pin IOxx — 已知风险：...` 注释；`// clang-format off` 包裹整文件。
