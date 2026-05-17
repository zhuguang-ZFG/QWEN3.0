#!/usr/bin/env python3
"""Generate multi-turn conversation training data for context retention."""

import json, os

OUTPUT = r"D:\GIT\multi_turn_data.json"

pairs = [
    # Scenario 1: CNC debugging session (3 turns)
    {"messages": [
        {"role":"user","content":"CNC雕刻机X轴不动了，主轴正常转"},
        {"role":"assistant","content":"X轴不动但主轴转 → 问题在X轴驱动器或步进电机。先检查：\n1. X轴步进驱动器电源灯亮吗？\n2. $100=320 这个值对吗？"},
        {"role":"user","content":"电源灯亮的，$100=320是正确的"},
        {"role":"assistant","content":"那查接线。重点查X轴驱动器的：\n- DIR+ / DIR- 和 PUL+ / PUL- 连线\n- ENA+ / ENA- 是否接反（如果接反会一直锁定不转）\n\n用万用表在PUL+上测，发G0 X10时应该有脉冲信号。"},
        {"role":"user","content":"果然ENA接反了，换了就好了。另外Y轴现在有异响"},
        {"role":"assistant","content":"Y轴异响通常是：\n1. 速度太快 → $111 降低 20%\n2. 加速太猛 → $121 降低到 50\n3. 机械共振 → Y轴丝杆加润滑，轴承检查\n\n试一下 $111=400, $121=40，跑10分钟看看还有没有异响。"},
    ]},
    # Scenario 2: ESP32 firmware development (2 turns)
    {"messages": [
        {"role":"user","content":"ESP32-S3怎么把PSRAM映射到数据空间？"},
        {"role":"assistant","content":"在 menuconfig 中开启：\n1. `CONFIG_SPIRAM=y`\n2. `CONFIG_SPIRAM_USE_MALLOC=y`\n3. `CONFIG_SPIRAM_MODE_OCT=y`\n\n代码：\n```c\n#include \"esp_psram.h\"\nvoid *ptr = heap_caps_malloc(1024*1024, MALLOC_CAP_SPIRAM);\n```\n需要更新 `sdkconfig`。"},
        {"role":"user","content":"编译报错 heap_caps_malloc 未定义"},
        {"role":"assistant","content":"缺少头文件。加上：\n```c\n#include \"esp_heap_caps.h\"\n```\n另外在 CMakeLists.txt 中确认链接了 `esp_psram` 组件。"},
    ]},
    # Scenario 3: SVG/GCode pipeline (2 turns)
    {"messages": [
        {"role":"user","content":"这个SVG文件转GCode后线条是锯齿状的"},
        {"role":"assistant","content":"锯齿 = 精度不够。检查：\n1. 你的 `svg2gcode` 的 `--tolerance` 参数（默认0.1mm，试试0.01）\n2. Potrace 的 `--opttolerance` 是否太低\n\n给我你的转换命令，我看看参数。"},
        {"role":"user","content":"用的 `svg2gcode input.svg --tolerance 0.5 --feed 500`"},
        {"role":"assistant","content":"--tolerance 0.5 太大了！每条线段之间偏差0.5mm，难怪锯齿。\n\n改成：\n```bash\nsvg2gcode input.svg --tolerance 0.02 --feed 500 --acceleration 100\n```\n\n如果文件很大导致GCode太大，先把SVG用 vpype 简化：\n```bash\nvpype read input.svg linemerge --tolerance 0.05 linesimplify --tolerance 0.02 write output.svg\n```"},
    ]},
    # Scenario 4: Reverse engineering discovery (3 turns)
    {"messages": [
        {"role":"user","content":"抓到一个串口协议的二进制数据，怎么分析？"},
        {"role":"assistant","content":"串口协议逆向步骤：\n1. 示波器测波特率 → 找最短脉冲宽度\n2. 逻辑分析仪抓100组完整数据\n3. 找帧头：100组中每帧开头都一样的几个字节\n4. 找长度字段：内容变长时哪个字节也变\n5. 找校验码：最后一个字节通常就是\n\n把数据发给我看看。"},
        {"role":"user","content":"帧头好像是AA55，第4字节变，最后一字节是FF"},
        {"role":"assistant","content":"AA55 是常见帧头。第4字节=长度字段。最后一字节FF → 不是校验码，可能是帧尾。\n\n校验可能在倒数第二字节。试试 CRC8 (polynomial 0x07) 验证：\n```python\nfor frame in frames:\n    crc = crc8(frame[1:-2])  # 去掉帧头帧尾\n    if crc == frame[-2]: print(\"CRC8 matched\")\n```"},
        {"role":"user","content":"CRC8验证通过了！现在能反推出协议结构了"},
        {"role":"assistant","content":"协议结构：\n```\n| AA55 (2B) | CMD (1B) | LEN (1B) | DATA (NB) | CRC8 (1B) | FF (1B) |\n```\n\n现在可以写解析器了。把CMD字段的值和功能列出来（比如0x01=读状态, 0x02=写参数等），然后逆向各个命令的数据格式。"},
    ]},
    # Scenario 5: Code review session (2 turns)
    {"messages": [
        {"role":"user","content":"这段步进电机代码为什么丢了步？\n```c\nvoid step_motor(void) {\n  digitalWrite(STEP_PIN, HIGH);\n  delayMicroseconds(10);\n  digitalWrite(STEP_PIN, LOW);\n  delay(1);  // wait 1ms\n}\n```"},
        {"role":"assistant","content":"`delay(1)` 在中间就是问题。步进脉冲时序必须精确对称：\n```c\nvoid step_motor(void) {\n  digitalWrite(STEP_PIN, HIGH);\n  delayMicroseconds(10);\n  digitalWrite(STEP_PIN, LOW);\n  delayMicroseconds(10);  // 10μs, NOT 1ms\n}\n```\n\n一毫秒停顿在50kHz频率下=丢了50个脉冲。"},
        {"role":"user","content":"换过后还是偶尔丢，频率高了就跑不准"},
        {"role":"assistant","content":"定时器中断方案替代 delay：\n```c\nhw_timer_t *timer = timerBegin(1000000);\ntimerAlarm(timer, 20, true, 0);  // 20μs = 50kHz\ntimerAttachInterrupt(timer, &step_isr);\n```\n\n结论：delayMicroseconds() 在 ESP32 上有约 2-5μs 抖动。高频场景必须用硬件定时器。"},
    ]},
]

def main():
    print(f"Generating {len(pairs)} multi-turn conversation examples...")
    json.dump(pairs, open(OUTPUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"Saved to {OUTPUT}")

if __name__ == "__main__":
    main()
