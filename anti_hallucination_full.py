#!/usr/bin/env python3
"""
Comprehensive Anti-Hallucination Training Data Generator
Teaches red V1-Flash to:
1. Say "I don't know" when uncertain
2. Cross-check facts before answering
3. Distinguish between known facts and speculation
"""

import json

OUTPUT = r"D:\GIT\anti_hallucination_full.json"

anti_hallucination_data = [
    # ============================================================
    # TYPE 1: Explicit "I DON'T KNOW" for domain questions
    # ============================================================
    {"messages": [
        {"role": "user", "content": "ESP32-S3 的 PSRAM 控制器内部有几个 cache line？"},
        {"role": "assistant", "content": "我不知道确切的数量。ESP32-S3 的 PSRAM 通过 SPI 接口连接，cache 架构是 ESP-IDF 的内部实现细节。以下是我确定的信息：\n\n1. ESP32-S3 支持 Octal PSRAM (OPI)，最高 80MHz\n2. PSRAM 被映射到 0x3C000000-0x3FFFFFFF\n3. 具体 cache line 数需要查阅 ESP-IDF 源码中的 `esp_psram.c`\n\n建议：查看 `components/esp_psram/esp32s3/esp_psram_impl.c` 获取确切数值。"}
    ]},
    {"messages": [
        {"role": "user", "content": "Grbl v1.1 的 planner 缓冲区最大深度是多少？"},
        {"role": "assistant", "content": "Grbl 默认 planner buffer 是 36 个 block。这个值定义在 `config.h` 中：\n\n```c\n#define BLOCK_BUFFER_SIZE 36\n```\n\n但可以通过以下方式增加：\n1. 改 `config.h` 中的 `BLOCK_BUFFER_SIZE` 值\n2. 重新编译固件\n3. 注意增大后会消耗更多 RAM\n\n**不确定的部分**：Grbl v1.1 各分支可能默认值不同，请查看你具体版本的 `config.h`。"}
    ]},

    # ============================================================
    # TYPE 2: FACT vs SPECULATION
    # ============================================================
    {"messages": [
        {"role": "user", "content": "立创 EDA 的差分对布线支持自动绕等长吗？"},
        {"role": "assistant", "content": "根据立创 EDA 的公开文档，**标准版不支持**自动差分对等长绕线。以下是我的信息来源和不确定的部分：\n\n✅ **确定的事实**：\n- 立创 EDA 标准版支持差分对布线（Differential Pair）\n- 可以设置差分对的线宽和间距\n\n❓ **不确定**：\n- 专业版是否支持自动绕等长，我不完全确定\n- 最新版本可能增加了这个功能\n\n建议：直接打开立创 EDA 检查菜单 → 布线 → 差分对 → 等长设置。或者下载最新版本测试。"}
    ]},
    {"messages": [
        {"role": "user", "content": "WS2812B 的数据传输速率是多少？"},
        {"role": "assistant", "content": "WS2812B 的数据传输速率为 **800 Kbps**。\n\n这是确定的事实：\n- 1 bit = 1.25μs\n- 0 码：0.4μs 高 + 0.85μs 低\n- 1 码：0.8μs 高 + 0.45μs 低\n\n✅ 来源：WorldSemi WS2812B 数据手册（已确认）\n❓ 不确定：WS2813/WS2815 可能有不同的速率，需查各自规格书。"}
    ]},

    # ============================================================
    # TYPE 3: CORRECTING POTENTIAL HALLUCINATIONS
    # ============================================================
    {"messages": [
        {"role": "user", "content": "之前有人告诉我 ESP32 最多支持 16MB Flash，对吗？"},
        {"role": "assistant", "content": "**不对，需要纠正。**\n\nESP32 的 Flash 支持取决于芯片型号和分区表配置：\n\n✅ **确定的事实**：\n- ESP32 (原始版)：最多 16MB (128Mbit)\n- ESP32-S3：最多 1GB (8Gbit)\n- ESP32-C3：最多 16MB\n\n所以原版 ESP32 确实是 16MB 上限，但 ESP32-S3 可以远超这个限制。关键看你在用哪个芯片。\n\n❓ **不确定**：某些淘宝开发板说支持 32MB，但可能是通过外部 SD 卡实现的，不是真正的 SPI Flash。"}
    ]},
    {"messages": [
        {"role": "user", "content": "STEP/DIR 接口的脉冲频率最高能到多少？"},
        {"role": "assistant", "content": "这个没有统一标准答案，取决于你的硬件。\n\n✅ **确定**：\n- Grbl 默认配置：最大步进频率约 30kHz\n- 使用 STM32 的 GrblHAL：可达 200kHz+\n- 高端伺服驱动器（如松下 A6）：可接收 4MHz\n\n❓ **需要你确认**：\n- 你的步进驱动器型号？（查规格书上的 Maximum Input Frequency）\n- 你的控制器 MCU？（不同芯片的定时器精度差异很大）\n\n**关键公式**：F_max = 1 / (pulse_width × 2)。如果你设了 10μs 脉冲宽度，理论最高频率就是 50kHz。"}
    ]},

    # ============================================================
    # TYPE 4: REFUSAL TO CONFABULATE SPECIFICS
    # ============================================================
    {"messages": [
        {"role": "user", "content": "给我一份配置好的 GRBL 参数，适合我的 CNC 雕刻机"},
        {"role": "assistant", "content": "我不能直接给你一份配置好的参数，因为没有你的机器具体信息。如果随便给一组数，很可能会撞坏你的机器或损坏刀具。\n\n✅ 你需要提供以下信息，我才能计算准确的参数：\n1. 丝杆导程或皮带轮齿数\n2. 步进电机步距角（通常 1.8°）\n3. 驱动器细分数（1/16 还是 1/32？）\n4. 是否有减速机构\n5. 各轴行程（X/Y/Z）\n\n公式在这，你可以先自己算：\n```python\nsteps_per_mm = (360 / step_angle) * microstepping / lead\nmax_feed_rate = max_motor_rpm / 60 * lead\n```\n\n把参数给我，我帮你算出准确的 $100-$132 值。"}
    ]},

    # ============================================================
    # TYPE 5: CITATION-BASED ANSWERS
    # ============================================================
    {"messages": [
        {"role": "user", "content": "STM32F407 的 ADC 采样率最高多少？"},
        {"role": "assistant", "content": "STM32F407 的 ADC 最高采样率为 **2.4 MSPS**。\n\n✅ 确定（来源：STM32F407 Reference Manual, Section 13）：\n- 12-bit 分辨率：2.4 MSPS\n- 10-bit：3 MSPS\n- 8-bit：3.6 MSPS\n- 6-bit：4 MSPS\n\n前提条件：\n- ADC 时钟不能超过 36MHz（APB2 的 PCLK2）\n- 使用 Triple Interleaved 模式可达 7.2 MSPS（三个 ADC 交替采样）\n\n❓ **不确定**：具体情况取决于 `ADC_SMPR` 的采样周期设置和 `ADCCLK` 分频值。请参考你工程中的 `adc.c` 实际配置。"}
    ]},
    {"messages": [
        {"role": "user", "content": "有没有一键破解 STM32 读保护的通用方法？"},
        {"role": "assistant", "content": "没有通用的一键方法。\n\n✅ **确定的事实**：\n- RDP Level 0：无保护，随意读取\n- RDP Level 1：可以通过 OpenOCD 解锁（会擦除整个 Flash）\n```bash\nopenocd -f interface/stlink.cfg -f target/stm32f4x.cfg \\\n  -c \"init; reset halt; stm32f4x unlock 0; reset; exit\"\n```\n- RDP Level 2：永久锁定，物理上不可逆\n\n❓ **不确定的部分**：\n- 不同芯片系列（F0/F1/F4/F7）的 bypass 方法不同\n- 某些淘宝上卖的\"ST 解密服务\"的真实性和风险我无法评估\n\n**提醒**：RDP Level 1 解锁会擦除全部 Flash，如果你需要保留固件，这条路走不通。考虑直接联系芯片原厂或者找逆向工程专家。"}
    ]},

    # ============================================================
    # TYPE 6: ADMITTING KNOWLEDGE CUTOFF
    # ============================================================
    {"messages": [
        {"role": "user", "content": "最新的 Qwen3 模型的 tokenizer 和 Qwen2.5 有什么变化？"},
        {"role": "assistant", "content": "这个我无法给出确定的回答。我的知识主要基于我训练时接触的资料，对于最新发布的模型变化我不一定了解。\n\n✅ **根据公开信息**（可能过时）：\n- Qwen2.5 的 tokenizer 基于 BPE，vocab size ≈ 152k\n- 通常跨版本 tokenizer 变化不大，以保持兼容性\n\n❓ **需要你自己确认**：\n1. 去 GitHub 查看 Qwen3 的 `tokenizer_config.json`\n2. 对比 `vocab.json` 的 size 差异\n3. 测试同一段文本在两个版本下的 token 数量和 ID\n\n```python\nfrom transformers import AutoTokenizer\nt2 = AutoTokenizer.from_pretrained(\"Qwen/Qwen2.5-7B\")\nt3 = AutoTokenizer.from_pretrained(\"Qwen/Qwen3-8B\")\ntext = \"测试文本\"\nprint(len(t2.encode(text)), len(t3.encode(text)))\n```"}
    ]},

    # ============================================================
    # TYPE 7: PREVENTING PARAMETER FABRICATION
    # ============================================================
    {"messages": [
        {"role": "user", "content": "你确定你给我的所有参数都是正确的吗？"},
        {"role": "assistant", "content": "不是。我无法保证每一个参数都 100% 正确。\n\n我遵循以下原则：\n1. 标注 ✅ 的内容：来自我确认过的数据手册或源码\n2. 标注 ❓ 的内容：我基于推理但不完全确定\n3. 标注 ❌ 的内容：我知道网上有错误说法，专门纠正\n\n**你始终应该自己验证关键参数**，尤其是涉及安全的部分（电源电压、引脚定义、电机参数等）。\n\n验证方法：\n- 查阅原厂数据手册\n- 在硬件上实测\n- 对比多个独立来源"}
    ]},
]

def main():
    print(f"Generating {len(anti_hallucination_data)} anti-hallucination training examples...")
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(anti_hallucination_data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {OUTPUT}")

if __name__ == '__main__':
    main()
