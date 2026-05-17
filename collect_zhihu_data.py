#!/usr/bin/env python3
"""
从 Hugging Face 下载知乎数据集并过滤领域相关内容。
数据集: wangrui6/Zhihu-KOL (几百万条知乎高赞回答)
过滤: CNC/嵌入式/ESP32/单片机/电子/编程/逆向 等领域关键词
输出: 追加到 round5_training_data.json
"""

import json, os, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTPUT = r"D:\GIT\round5_training_data.json"
CACHE_DIR = r"D:\GIT\hf_cache"

# 领域关键词 — 命中任意一个即保留
DOMAIN_KEYWORDS = [
    # CNC / 数控
    "CNC", "数控", "G代码", "G-code", "Gcode", "数控机床", "加工中心",
    "铣床", "车床", "主轴", "进给", "刀具补偿", "对刀", "grbl", "Marlin",
    # 嵌入式 / 单片机
    "ESP32", "ESP8266", "Arduino", "STM32", "单片机", "嵌入式", "MCU",
    "RTOS", "FreeRTOS", "HAL库", "寄存器", "中断", "DMA", "SPI", "I2C",
    "UART", "PWM", "ADC", "DAC", "GPIO", "固件", "烧录", "Keil", "IAR",
    # 电子 / 硬件
    "PCB", "原理图", "示波器", "逻辑分析仪", "电路", "运放", "MOSFET",
    "电源设计", "EMC", "滤波", "降压", "升压", "锂电池",
    # 编程 / 逆向
    "逆向工程", "反汇编", "IDA Pro", "Ghidra", "调试器", "汇编",
    "Python", "C语言", "C++", "Rust", "Go语言",
    # 3D打印
    "3D打印", "切片", "FDM", "打印机固件",
]

KEYWORD_PATTERN = re.compile("|".join(re.escape(k) for k in DOMAIN_KEYWORDS), re.IGNORECASE)

MIN_ANSWER_LEN = 100   # 回答最短字符数
MAX_ANSWER_LEN = 2000  # 回答最长字符数（避免超长文本）
MAX_SAMPLES = 50000    # 最多采集条数


def is_relevant(text: str) -> bool:
    return bool(KEYWORD_PATTERN.search(text))


def clean_text(text: str) -> str:
    # 去除多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def load_existing() -> list:
    if os.path.exists(OUTPUT):
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save(data: list):
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("  知乎数据采集 — wangrui6/Zhihu-KOL")
    print("=" * 60)

    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: pip install datasets")
        return

    print(f"\n[1] 加载数据集 (缓存到 {CACHE_DIR})...")
    os.makedirs(CACHE_DIR, exist_ok=True)

    try:
        ds = load_dataset(
            "wangrui6/Zhihu-KOL",
            split="train",
            cache_dir=CACHE_DIR,
            trust_remote_code=True,
        )
    except Exception as e:
        print(f"ERROR 加载数据集: {e}")
        print("尝试备用数据集 BAAI/COIG-CQIA ...")
        try:
            ds = load_dataset(
                "BAAI/COIG-CQIA",
                name="zhihu",
                split="train",
                cache_dir=CACHE_DIR,
                trust_remote_code=True,
            )
        except Exception as e2:
            print(f"ERROR 备用数据集也失败: {e2}")
            return

    print(f"  数据集大小: {len(ds):,} 条")

    print(f"\n[2] 过滤领域相关内容...")
    existing = load_existing()
    existing_set = {
        item['messages'][0]['content'][:80]
        for item in existing
        if isinstance(item, dict) and 'messages' in item
    }

    new_pairs = []
    checked = 0

    for row in ds:
        if len(new_pairs) >= MAX_SAMPLES:
            break

        checked += 1
        if checked % 100000 == 0:
            print(f"  已检查 {checked:,} 条，命中 {len(new_pairs):,} 条...")

        # 尝试不同字段名
        question = (
            row.get('INSTRUCTION') or row.get('question') or
            row.get('title') or row.get('prompt') or ""
        )
        answer = (
            row.get('RESPONSE') or row.get('answer') or
            row.get('content') or row.get('response') or ""
        )

        if not question or not answer:
            continue

        question = clean_text(str(question))
        answer = clean_text(str(answer))

        if len(answer) < MIN_ANSWER_LEN or len(answer) > MAX_ANSWER_LEN:
            continue

        combined = question + " " + answer
        if not is_relevant(combined):
            continue

        # 去重
        key = question[:80]
        if key in existing_set:
            continue
        existing_set.add(key)

        new_pairs.append({
            "messages": [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        })

    print(f"\n[3] 结果: 检查 {checked:,} 条，命中 {len(new_pairs):,} 条")

    if new_pairs:
        existing.extend(new_pairs)
        save(existing)
        print(f"  已追加到 {OUTPUT}")
        print(f"  总数据量: {len(existing):,} 条")
    else:
        print("  未找到匹配数据，检查关键词或数据集字段名")

    print("\n完成")


if __name__ == "__main__":
    main()
