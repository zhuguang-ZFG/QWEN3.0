#!/usr/bin/env python3
"""
Reverse Engineering & Tool Calling Training Data for red V1-Flash.
Teaches the model RE techniques and tool-use patterns.
"""

import json

OUTPUT = r"D:\GIT\reverse_engineering_training_data.json"

pairs = [
    # ============================================================
    # FIRMWARE REVERSE ENGINEERING
    # ============================================================
    {
        "messages": [
            {"role": "user", "content": "如何从 ESP32 的 flash 中 dump 出固件？"},
            {"role": "assistant", "content": "ESP32 固件 dump 步骤：\n\n1. **通过 UART**：\n```bash\nesptool.py --port COM3 --baud 115200 read_flash 0 0x400000 flash_dump.bin\n```\n这会从地址 0 开始读取 4MB flash。\n\n2. **通过 JTAG**：\n```bash\nopenocd -f interface/ftdi/esp32_devkitj_v1.cfg -f target/esp32.cfg\n# 在另一个终端\ntelnet localhost 4444\nesp32 appimage_offset 0x10000\nflash read_bank 0 dump.bin 0 0x400000\n```\n\n3. **分析提取的固件**：\n```bash\n# 提取分区表\nesptool.py --chip esp32 parse_partition_table flash_dump.bin\n# 用 strings 找敏感信息\nstrings flash_dump.bin | grep -E 'wifi|password|key|token'\n```"}
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "提取 STM32 固件的方法有哪些？"},
            {"role": "assistant", "content": "STM32 固件提取：\n\n**读保护（RDP）绕过**：\n\n1. **RDP Level 0**（默认）：\n```bash\nopenocd -f interface/stlink.cfg -f target/stm32f4x.cfg\nflash read_bank 0 firmware.bin 0 0x100000\n```\n\n2. **RDP Level 1**：\n- 电压毛刺攻击（Voltage Glitching）：在 flash 读取时给 VDD 施加短暂低压脉冲\n- 芯片拆壳后用 UV 光擦除 RDP 位（老芯片有效）\n- F0/F1 系列：通过 Bootloader + 特定时序可绕过\n\n3. **RDP Level 2**：物理不可逆，只能拆芯片用微探针\n\n**SWD 禁止后的恢复**：\n- MCU 启动后前~100ms SWD 仍可用（在执行到禁 SWD 的代码之前）\n- 供电时在 NRST 上接 GND，启动瞬间释放可进入调试模式\n\nST-Link Utility 命令：\n```bash\nST-LINK_CLI.exe -c SWD -r8 0x08000000 0x100000 firmware.bin\n```"}
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "如何分析 ARM Cortex-M 的固件二进制文件？从裸二进制到反汇编"},
            {"role": "assistant", "content": "ARM 固件分析流程：\n\n1. **确定加载地址**：\n```python\n# 从向量表找基地址\nwith open('firmware.bin', 'rb') as f:\n    sp = struct.unpack('<I', f.read(4))[0]      # 初始 SP\n    reset_handler = struct.unpack('<I', f.read(4))[0]  # Reset 入口\n    print(f\"SP: 0x{sp:08X}, Entry: 0x{reset_handler:08X}\")\n    # 入口地址 & 0xFFFFFFFE 就是加载基地址\n    base = reset_handler & 0xFFFFFFFE - 0x200\n```\n\n2. **Ghidra 加载**：\n- File → Import → 选 firmware.bin\n- Language: ARM:LE:32:Cortex\n- Base Address: 上面算出的 base\n\n3. **自动分析**：\n- 按 D 在向量表区域定义数据\n- Search → For Address Tables 找跳转表\n- Window → Symbol Table → 创建函数\n\n4. **关键分析点**：\n```c\n// 找 main() - 通常在 Reset_Handler 中被调用\nReset_Handler:\n    LDR R0, =main\n    BLX R0\n\n// 找外设初始化 - 大量 LDR/STR 到 0x40000000 范围\n// 0x40000000-0x5FFFFFFF 是 APB/AHB 外设总线\n```"}
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "用 Ghidra 分析 ARM 固件，找不到函数的地址怎么恢复？"},
            {"role": "assistant", "content": "恢复符号和函数的技巧：\n\n1. **利用 CMSIS 头文件**：\n```python\n# 用 Python 脚本给外设寄存器命名\ncm4_svd = {\n    0x40023800: \"RCC_BASE\",\n    0x40020000: \"GPIOA_BASE\",\n    0x40011000: \"USART1_BASE\",\n}\nfor addr, name in cm4_svd.items():\n    createLabel(addr, name, True)\n```\n\n2. **从中断向量表恢复 ISR**：\n向量表第 16+ 个条目就是各个中断的 ISR 地址\n\n3. **找编译器特征**：\n- ARMCC: `__main`, `__scatterload`\n- GCC: `_start`, `__libc_init_array`\n- IAR: `__iar_program_start`\n\n4. **字符串交叉引用**：\n在 Ghidra 中搜索 ASCII 字符串 → 右键 References → Show References to Address\n通常错误字符串附近的代码就是对应的处理函数"}
        ]
    },

    # ============================================================
    # PROTOCOL REVERSE ENGINEERING
    # ============================================================
    {
        "messages": [
            {"role": "user", "content": "如何逆向一个未知的串口通信协议？有逻辑分析仪和示波器"},
            {"role": "assistant", "content": "未知串口协议逆向流程：\n\n1. **物理层识别**：\n- 用示波器测信号电压（RS232 ±12V, TTL 0-5V, RS485 差分）\n- 测波特率：找最短脉冲宽度 → B = 1/T\n- 逻辑分析仪抓取信号\n\n2. **数据格式分析**：\n```python\nfrom pyserial import Serial\nser = Serial('COM3', 115200, timeout=1)\nraw = ser.read(1024)\n[print(f\"{b:02X}\", end=' ') for b in raw[:100]]\n```\n\n3. **协议逆向**：\n- 找帧头/帧尾：重复出现的固定字节序列\n- 找长度字段：随数据量变化的特定字节\n- 找校验码：通常最后一个或倒数第二个字节\n```python\n# CRC8 校验试探\nfor poly in [0x07, 0x31, 0x8D, 0x1D]:\n    crc = crc8(poly, data[:-1])\n    if crc == data[-1]:\n        print(f\"CRC8 poly=0x{poly:02X} matched\")\n```\n\n4. **用 Sigrok + PulseView**：\n- 选 UART 解码器\n- 如果数据有规律，切换为自定义协议解码\n- 导出为 CSV 进一步分析"}
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "怎么破解 SPI Flash 里的加密固件？厂商用了 AES"},
            {"role": "assistant", "content": "Flash 加密固件逆向路径：\n\n1. **确认加密方式**：\n```bash\n# Dump flash\nflashrom -p ch341a_spi -r dump.bin\n# 检查熵值，高熵 = 加密/压缩\nbinwalk -E dump.bin\n# 熵 > 7.5 通常就是加密了\n```\n\n2. **找密钥来源**：\n- ESP32: Key 存储在 eFuse BLOCK1\n- STM32: 存储在 OTP 区域或外部安全芯片\n- 通用: 从固件更新包（OTA）中找解密逻辑\n\n3. **侧信道攻击**（需要物理接触）：\n```python\n# 差分功率分析 (DPA) 攻击 AES\n# 需要在芯片供电线上采样\nimport numpy as np\n# 收集 1000 次加密操作的功率曲线\ntraces = [np.array(trace) for trace in captured_traces]\n# 用猜测的密钥字节遍历 SBOX 输出\nfor key_guess in range(256):\n    correlation = correlate(traces, hamming_weight_model(key_guess))\n    if correlation > threshold:\n        print(f\"Key byte candidate: {key_guess}\")\n```\n\n4. **找 OTA 更新包**：\n- 抓取手机 App 与设备的 BLE 通信\n- OTA 包通常不加密传输，只在 flash 上加密存储\n- 从 OTA 包中提取明文固件"}
        ]
    },

    # ============================================================
    # TOOL CALLING CAPABILITIES
    # ============================================================
    {
        "messages": [
            {"role": "user", "content": "你有哪些可用的工具？"},
            {"role": "assistant", "content": "我有以下工具可用：\n\n1. **文件操作**：Read, Write, Edit - 读取/创建/编辑文件\n2. **代码搜索**：Grep, Glob - 搜索代码内容和文件名\n3. **命令执行**：Bash - 运行任意 shell 命令\n4. **Web 抓取**：WebFetch, WebSearch - 访问网页和搜索\n5. **任务管理**：TaskCreate, TaskUpdate - 创建和跟踪任务\n6. **代理调用**：Agent - 启动专门的子代理处理复杂任务\n\n要使用这些工具，直接告诉我你的需求即可，我会选择合适的工具执行。"}
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "帮我分析这个目录下的固件二进制文件 D:\\firmware\\unknown.bin"},
            {"role": "assistant", "content": "立刻开始分析。\n\n第一步：检查文件基本信息。\n```bash\n# 查看文件大小和熵值\nfile D:/firmware/unknown.bin\nbinwalk D:/firmware/unknown.bin\nstrings D:/firmware/unknown.bin | head -50\n```\n\n第二步：如果是 ARM 固件，确定加载地址：\n```python\nwith open('D:/firmware/unknown.bin', 'rb') as f:\n    header = f.read(256)\n    sp, entry = struct.unpack('<II', header[:8])\n    print(f\"Stack Pointer: 0x{sp:08X}\")\n    print(f\"Entry Point: 0x{entry:08X}\")\n```\n\n第三步：用 Ghidra 加载分析。\n需要的话我现在就开始执行这些命令。"}
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "帮我在整个项目中搜索所有包含密码或密钥的地方"},
            {"role": "assistant", "content": "我会搜索多种模式：\n\n```bash\n# 搜索硬编码的密码/密钥\ngrep -r \"password\\|passwd\\|secret\\|api_key\\|token\" \\\n  --include=\"*.c\" --include=\"*.h\" --include=\"*.py\" --include=\"*.js\" \\\n  --include=\"*.cpp\" --include=\"*.json\" --include=\"*.yaml\" --include=\"*.env\" .\n\n# 搜索常见的密钥模式（Base64、Hex）\ngrep -rP \"[A-Za-z0-9+/]{32,}={0,2}\" --include=\"*.c\" --include=\"*.h\" .\ngrep -rP \"0x[0-9A-Fa-f]{16,}\" --include=\"*.c\" --include=\"*.h\" .\n\n# 搜索硬编码的 IP、URL\ngrep -rP \"\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\" --include=\"*.c\" --include=\"*.h\" .\n\n# 检查 .git 历史中是否有泄露\ngit log --all --full-history -- \"*.env\" \"*.pem\" \"*.key\"\n```"}
        ]
    },

    # ============================================================
    # JTAG / DEBUG INTERFACE
    # ============================================================
    {
        "messages": [
            {"role": "user", "content": "ESP32 的 JTAG 被禁用了，怎么重新启用？"},
            {"role": "assistant", "content": "ESP32 JTAG 禁用后的绕过方法：\n\n1. **检查 eFuse 状态**：\n```bash\nespefuse.py --port COM3 summary\n# 重点看: JTAG_DISABLE, DISABLE_JTAG\n```\n\n2. **如果 JTAG 被软件禁用**（不是 eFuse）：\n- 在代码中的 `gpio_reset_pin()` 或 `rtc_gpio_isolate()` 之后重新配置 JTAG 引脚\n- 可能在 bootloader 阶段被禁用\n- 用 esptool 擦除整个 flash，刷一个 JTAG 未禁用的固件\n\n3. **eFuse 烧了 JTAG_DISABLE**：\n- 唯一方法是物理攻击：拆芯片，用 FIB (Focused Ion Beam) 修改 eFuse 区域\n- 或者用电压注入强制跳过 eFuse 检测\n\n4. **变通方案**：\n- 用 UART 0 下载模式：IO0 接 GND，可以进入下载模式\n- 在固件中嵌入后门（如果你能改源码）\n```c\n// 在 app_main 开头加后门\nif (gpio_get_level(GPIO_NUM_4) == 0) {\n    esp_bt_controller_disable();\n    // 不初始化 JTAG 禁用代码\n}\n```"}
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "OpenOCD 连接 STM32 报错 'Cannot access memory' 怎么解决？"},
            {"role": "assistant", "content": "OpenOCD 'Cannot access memory' 解决方案：\n\n1. **RDP 保护检查**：\n```bash\nopenocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"init; stm32f4x options_read 0; exit\"\n# 查看 RDP 等级\n```\n\n2. **RDP Level 1 解锁**：\n```bash\nopenocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \\\n  \"init; reset halt; stm32f4x unlock 0; reset; exit\"\n# 警告：这会擦除整个 flash！\n```\n\n3. **RDP Level 2**：永久锁定，无法通过 SWD 解锁\n\n4. **SWD 连接问题排查**：\n- 确保 NRST 连接（有些 MCU 需要硬件复位才能进入调试）\n- SWCLK 频率降低：`adapter speed 100`\n- 检查是否有其他软件占用了调试器（ST-Link Utility, IAR, Keil）\n- 尝试 power-down mode: `cortex_m reset_config vectreset`"}
        ]
    },

    # ============================================================
    # TOOL USE WITH CLAUDE
    # ============================================================
    {
        "messages": [
            {"role": "user", "content": "用代码搜索工具在所有 .c 文件中找 USART 初始化代码"},
            {"role": "assistant", "content": "直接搜索：\n```\ngrep -rn \"USART_Init\\|HAL_UART_Init\\|uart_init\\|USART1_Init\" \\\n  --include=\"*.c\" --include=\"*.h\" --include=\"*.cpp\" .\n```\n\n如果需要更精确的搜索，可以指定目录：\n```\ngrep -rn \"MX_USART\" --include=\"*.c\" ./Core/Src/\ngrep -rn \"huart\" --include=\"*.c\" ./Drivers/\n```"}
        ]
    },
    {
        "messages": [
            {"role": "user", "content": "帮我抓取这个芯片的数据手册网页 https://example.com/datasheet 并提取关键参数"},
            {"role": "assistant", "content": "我来抓取页面并提取关键信息：\n\n```bash\n# 获取页面内容\ncurl -s \"https://example.com/datasheet\" -o datasheet.html\n# 提取文本\npython -c \"\nfrom bs4 import BeautifulSoup\nsoup = BeautifulSoup(open('datasheet.html'), 'html.parser')\nfor table in soup.find_all('table'):\n    print(table.get_text())\n\"\n```\n\n然后提取这些关键参数：\n- 工作电压范围\n- 最大频率\n- 引脚功能定义\n- I/O 电气特性\n- 封装尺寸"}
        ]
    },
]

def main():
    print(f"Generating {len(pairs)} RE + tool-calling training pairs...")
    json.dump(pairs, open(OUTPUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"Saved to {OUTPUT}")
    print("Topics covered:")
    print("  - Firmware extraction (ESP32, STM32)")
    print("  - Binary analysis with Ghidra")
    print("  - Protocol reverse engineering")
    print("  - Flash encryption bypass")
    print("  - JTAG/SWD unlock")
    print("  - Tool calling patterns")

if __name__ == '__main__':
    main()
