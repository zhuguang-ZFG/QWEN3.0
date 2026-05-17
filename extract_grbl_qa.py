#!/usr/bin/env python3
"""
GRBL Q&A Training Data Generator
Generates Chinese Q&A pairs covering GRBL configuration, G-code commands,
error codes, real-time commands, and Grbl_Esp32 specific features.
Saves to D:/GIT/grbl_qa_data.json.
"""

import os
import json
import time
import urllib.request
from dotenv import load_dotenv
load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_FILE = "D:/GIT/grbl_qa_data.json"
CHECKPOINT_FILE = "D:/GIT/grbl_qa_checkpoint.json"
MODEL = "claude-sonnet-4-6"
API_URL = "https://right.codes/claude-aws/v1/messages"
CHECKPOINT_EVERY = 10
RATE_LIMIT_DELAY = 0.3

# ── Q&A Topic Definitions ─────────────────────────────────────────────────────

GRBL_SETTINGS = [
    ("$0", "步进脉冲时间 (Step pulse time, μs)"),
    ("$1", "步进空闲延迟 (Step idle delay, ms)"),
    ("$2", "步进端口反转掩码 (Step port invert mask)"),
    ("$3", "方向端口反转掩码 (Direction port invert mask)"),
    ("$4", "步进使能反转 (Step enable invert)"),
    ("$5", "限位引脚反转 (Limit pins invert)"),
    ("$6", "探针引脚反转 (Probe pin invert)"),
    ("$10", "状态报告掩码 (Status report mask)"),
    ("$11", "结点偏差 (Junction deviation, mm)"),
    ("$12", "圆弧容差 (Arc tolerance, mm)"),
    ("$13", "报告英寸 (Report inches)"),
    ("$20", "软限位 (Soft limits)"),
    ("$21", "硬限位 (Hard limits)"),
    ("$22", "归零循环 (Homing cycle)"),
    ("$23", "归零方向反转掩码 (Homing dir invert mask)"),
    ("$24", "归零进给速率 (Homing feed rate, mm/min)"),
    ("$25", "归零寻找速率 (Homing seek rate, mm/min)"),
    ("$26", "归零去抖延迟 (Homing debounce delay, ms)"),
    ("$27", "归零拉离距离 (Homing pull-off distance, mm)"),
    ("$30", "主轴最大转速 (Max spindle speed, RPM)"),
    ("$31", "主轴最小转速 (Min spindle speed, RPM)"),
    ("$32", "激光模式 (Laser mode)"),
    ("$100", "X轴步进数/mm (X steps/mm)"),
    ("$101", "Y轴步进数/mm (Y steps/mm)"),
    ("$102", "Z轴步进数/mm (Z steps/mm)"),
    ("$110", "X轴最大速率 (X max rate, mm/min)"),
    ("$111", "Y轴最大速率 (Y max rate, mm/min)"),
    ("$112", "Z轴最大速率 (Z max rate, mm/min)"),
    ("$120", "X轴加速度 (X acceleration, mm/s²)"),
    ("$121", "Y轴加速度 (Y acceleration, mm/s²)"),
    ("$122", "Z轴加速度 (Z acceleration, mm/s²)"),
    ("$130", "X轴最大行程 (X max travel, mm)"),
    ("$131", "Y轴最大行程 (Y max travel, mm)"),
    ("$132", "Z轴最大行程 (Z max travel, mm)"),
]

GCODE_COMMANDS = [
    ("G0", "快速定位移动 (Rapid positioning)"),
    ("G1", "线性插补进给 (Linear interpolation feed)"),
    ("G2", "顺时针圆弧插补 (Clockwise arc)"),
    ("G3", "逆时针圆弧插补 (Counter-clockwise arc)"),
    ("G4", "暂停/停留 (Dwell/pause)"),
    ("G10 L2", "设置工件坐标系原点 (Set work coordinate origin)"),
    ("G17", "选择XY平面 (Select XY plane)"),
    ("G18", "选择XZ平面 (Select XZ plane)"),
    ("G19", "选择YZ平面 (Select YZ plane)"),
    ("G20", "英制单位 (Inch units)"),
    ("G21", "公制单位 (Metric units)"),
    ("G28", "返回机器原点 (Return to machine home)"),
    ("G30", "返回第二原点 (Return to secondary home)"),
    ("G38.2", "探针向目标移动，接触停止 (Probe toward workpiece)"),
    ("G38.3", "探针向目标移动，接触不报错 (Probe toward, no error)"),
    ("G38.4", "探针离开目标 (Probe away from workpiece)"),
    ("G38.5", "探针离开，接触不报错 (Probe away, no error)"),
    ("G54-G59", "工件坐标系选择 (Work coordinate system selection)"),
    ("G80", "取消固定循环 (Cancel canned cycle)"),
    ("G90", "绝对坐标模式 (Absolute positioning)"),
    ("G91", "相对坐标模式 (Relative/incremental positioning)"),
    ("G92", "设置坐标系偏移 (Set coordinate offset)"),
    ("G93", "反时间进给模式 (Inverse time feed mode)"),
    ("G94", "每分钟进给模式 (Feed per minute mode)"),
    ("M0", "程序暂停 (Program pause)"),
    ("M2", "程序结束 (Program end)"),
    ("M3", "主轴正转/激光开 (Spindle CW / Laser on)"),
    ("M4", "主轴反转/激光动态模式 (Spindle CCW / Laser dynamic)"),
    ("M5", "主轴停止/激光关 (Spindle stop / Laser off)"),
    ("M7", "雾化冷却液开 (Mist coolant on)"),
    ("M8", "冷却液开 (Flood coolant on)"),
    ("M9", "冷却液关 (Coolant off)"),
    ("M30", "程序结束并复位 (Program end and reset)"),
]

GRBL_ERRORS = [
    (1, "G代码字母后缺少数值"),
    (2, "数控代码行超过最大字符数"),
    (3, "G代码字母后的数值无效"),
    (4, "负值无效"),
    (5, "归零未使能，无法执行G28/G30"),
    (6, "最小步进脉冲时间必须大于3微秒"),
    (7, "EEPROM读取失败，使用默认值"),
    (8, "GRBL '$' 命令在运行状态下不可用"),
    (9, "G代码命令在锁定状态下不可用"),
    (10, "软限位需要先完成归零"),
    (11, "最大字符数超限"),
    (12, "GRBL '$' 设置超出范围"),
    (13, "无效的GRBL '$' 设置"),
    (14, "无效的GRBL '$' 命令"),
    (15, "G代码字母重复"),
    (16, "模态组违规"),
    (17, "进给速率未定义"),
    (18, "无效的G代码ID"),
    (19, "无效的M代码ID"),
    (20, "未定义的进给速率"),
    (21, "G代码命令需要整数值"),
    (22, "多个G代码命令使用轴字"),
    (23, "进给速率未设置"),
    (24, "G代码字母在当前模式下无效"),
    (25, "G代码命令冲突"),
    (26, "第六轴字母无效"),
    (27, "无效的行号"),
    (28, "G代码命令缺少值字"),
    (29, "G59.x工件坐标不支持"),
    (30, "G53只在G0/G1模式下有效"),
    (31, "不必要的轴字"),
    (32, "G2/G3圆弧半径误差过大"),
    (33, "运动命令目标无效"),
    (34, "圆弧半径为负"),
    (35, "当前平面不支持G2/G3"),
    (36, "无效的目标"),
    (37, "刀具半径补偿不支持"),
    (38, "G43.1刀具长度偏置轴无效"),
    (39, "刀具长度偏置轴不支持"),
]

GRBL_ALARMS = [
    (1, "硬限位触发"),
    (2, "软限位触发"),
    (3, "复位时步进器未完成"),
    (4, "探针失败：初始状态已触发"),
    (5, "探针失败：未接触工件"),
    (6, "归零失败：复位清除"),
    (7, "归零失败：门开启"),
    (8, "归零失败：拉离失败"),
    (9, "归零失败：未找到限位开关"),
    (10, "主轴控制失败"),
    (11, "控制引脚初始化失败"),
]

REALTIME_COMMANDS = [
    ("?", "查询当前状态报告（位置、速度、状态）"),
    ("~", "循环启动/恢复暂停的运动"),
    ("!", "进给保持（暂停所有运动）"),
    ("Ctrl-X (0x18)", "软复位（重置GRBL控制器）"),
    ("0x84", "安全门触发（停止并等待）"),
    ("0x85", "慢速点动覆盖"),
    ("0x90", "进给速率覆盖100%（恢复默认）"),
    ("0x91", "进给速率覆盖+10%"),
    ("0x92", "进给速率覆盖-10%"),
    ("0x93", "进给速率覆盖+1%"),
    ("0x94", "进给速率覆盖-1%"),
    ("0x95", "快速速率覆盖100%"),
    ("0x96", "快速速率覆盖50%"),
    ("0x97", "快速速率覆盖25%"),
    ("0x99", "主轴转速覆盖100%"),
    ("0x9A", "主轴转速覆盖+10%"),
    ("0x9B", "主轴转速覆盖-10%"),
    ("0x9C", "主轴转速覆盖+1%"),
    ("0x9D", "主轴转速覆盖-1%"),
    ("0xA0", "切换主轴停止覆盖"),
    ("0xA1", "切换冷却液雾化"),
    ("0xA2", "切换冷却液液体"),
]

ESP32_FEATURES = [
    ("WiFi AP模式", "Grbl_Esp32支持WiFi接入点模式，允许设备创建自己的WiFi热点，用户可直接连接进行无线控制"),
    ("WiFi STA模式", "Grbl_Esp32支持WiFi站点模式，可连接到现有WiFi网络，通过局域网进行控制"),
    ("WebUI界面", "Grbl_Esp32内置Web用户界面，通过浏览器即可访问控制面板，无需安装额外软件"),
    ("蓝牙支持", "Grbl_Esp32支持蓝牙串口通信，可通过蓝牙连接手机或电脑进行控制"),
    ("SD卡支持", "Grbl_Esp32支持SD卡，可从SD卡读取G代码文件并执行，适合长时间加工任务"),
    ("I2S步进输出", "Grbl_Esp32使用ESP32的I2S外设生成步进脉冲，可驱动更多轴且不占用主CPU"),
    ("自定义引脚映射", "Grbl_Esp32允许通过配置文件自定义各功能引脚，适配不同硬件设计"),
    ("Trinamic驱动支持", "Grbl_Esp32原生支持TMC2130/TMC2208等Trinamic步进驱动器，支持SPI/UART配置"),
    ("动态主轴控制", "Grbl_Esp32支持多种主轴类型：PWM、DAC、激光、VFD变频器、Huanyang变频器等"),
    ("OTA固件更新", "Grbl_Esp32支持通过WiFi进行OTA（空中下载）固件更新，无需物理连接"),
    ("ESP32双核利用", "Grbl_Esp32利用ESP32的双核架构，将实时运动控制和通信任务分配到不同核心"),
    ("SPIFFS文件系统", "Grbl_Esp32使用ESP32的SPIFFS文件系统存储配置文件和WebUI静态资源"),
]

# ── Topic Builders ────────────────────────────────────────────────────────────

def build_topics() -> list[dict]:
    """Build all Q&A topic prompts."""
    topics = []

    # GRBL settings
    for param, desc in GRBL_SETTINGS:
        topics.append({
            "category": "grbl_settings",
            "key": param,
            "prompt": (
                f"请用中文详细解释GRBL参数 {param}（{desc}）的作用、"
                f"典型取值范围、如何设置以及设置不当会有什么影响。"
                f"请给出实际使用示例。"
            ),
            "user_q": f"GRBL参数 {param} 是什么意思？如何正确设置？",
        })

    # G-code commands
    for cmd, desc in GCODE_COMMANDS:
        topics.append({
            "category": "gcode_commands",
            "key": cmd,
            "prompt": (
                f"请用中文详细解释G代码指令 {cmd}（{desc}）在GRBL中的用法、"
                f"参数格式、使用场景和注意事项。请给出具体的代码示例。"
            ),
            "user_q": f"GRBL中 {cmd} 指令怎么用？",
        })

    # Error codes
    for code, desc in GRBL_ERRORS:
        topics.append({
            "category": "grbl_errors",
            "key": f"error:{code}",
            "prompt": (
                f"请用中文解释GRBL错误代码 error:{code}（{desc}）的含义、"
                f"常见触发原因以及解决方法。"
            ),
            "user_q": f"GRBL报告 error:{code} 是什么错误？怎么解决？",
        })

    # Alarm codes
    for code, desc in GRBL_ALARMS:
        topics.append({
            "category": "grbl_alarms",
            "key": f"alarm:{code}",
            "prompt": (
                f"请用中文解释GRBL报警代码 ALARM:{code}（{desc}）的含义、"
                f"触发条件、安全处理步骤以及如何预防。"
            ),
            "user_q": f"GRBL出现 ALARM:{code} 报警怎么办？",
        })

    # Real-time commands
    for cmd, desc in REALTIME_COMMANDS:
        topics.append({
            "category": "realtime_commands",
            "key": cmd,
            "prompt": (
                f"请用中文解释GRBL实时命令 {cmd}（{desc}）的功能、"
                f"使用时机和注意事项。说明它与普通G代码命令的区别。"
            ),
            "user_q": f"GRBL实时命令 {cmd} 有什么用？什么时候使用？",
        })

    # ESP32 features
    for feature, desc in ESP32_FEATURES:
        topics.append({
            "category": "esp32_features",
            "key": feature,
            "prompt": (
                f"请用中文详细介绍Grbl_Esp32的{feature}功能：{desc}。"
                f"说明如何配置和使用，以及与标准GRBL的区别。"
            ),
            "user_q": f"Grbl_Esp32的{feature}功能怎么使用？",
        })

    return topics


# ── Claude API ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "你是一位精通CNC数控加工、GRBL固件和嵌入式系统的中文技术专家。"
    "你的回答应该准确、实用，面向有一定基础的CNC爱好者和工程师。"
    "回答要简洁清晰，重点突出，适当使用示例代码或数值。"
)


def generate_answer(api_key: str, topic: dict) -> str:
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": topic["prompt"]}],
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["content"][0]["text"].strip()


def make_qa_pair(topic: dict, answer: str) -> dict:
    return {
        "messages": [
            {"role": "user", "content": topic["user_q"]},
            {"role": "assistant", "content": answer},
        ],
        "metadata": {
            "category": topic["category"],
            "key": topic["key"],
        },
    }


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def load_checkpoint() -> tuple[list, set]:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = data.get("results", [])
        done = set(data.get("done_keys", []))
        print(f"  Resumed from checkpoint: {len(results)} items already done.")
        return results, done
    return [], set()


def save_checkpoint(results: list, done: set) -> None:
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump({"results": results, "done_keys": list(done)}, f,
                  ensure_ascii=False, indent=2)


def save_final(results: list) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved {len(results)} Q&A pairs to {OUTPUT_FILE}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(test_mode: bool = False):
    api_key = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("CLAUDE_API_KEY or ANTHROPIC_API_KEY environment variable not set.")

    topics = build_topics()
    print(f"Total Q&A topics: {len(topics)}")

    if test_mode:
        # Pick 3 diverse topics for testing
        test_topics = [
            next(t for t in topics if t["category"] == "grbl_settings"),
            next(t for t in topics if t["category"] == "gcode_commands"),
            next(t for t in topics if t["category"] == "esp32_features"),
        ]
        topics = test_topics
        print(f"  TEST MODE: processing {len(topics)} topics.")

    results, done_keys = load_checkpoint()
    pending = [t for t in topics if t["key"] not in done_keys]
    print(f"  {len(pending)} topics to process.")

    for i, topic in enumerate(pending):
        print(f"  [{i+1}/{len(pending)}] [{topic['category']}] {topic['key']}...")
        try:
            answer = generate_answer(api_key, topic)
            pair = make_qa_pair(topic, answer)
            results.append(pair)
            done_keys.add(topic["key"])

            if (len(results) % CHECKPOINT_EVERY) == 0:
                save_checkpoint(results, done_keys)
                print(f"    Checkpoint saved ({len(results)} items).")

            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            print(f"    [ERROR] {topic['key']}: {e}")
            time.sleep(2)
            continue

    save_final(results)
    if os.path.exists(CHECKPOINT_FILE) and not test_mode:
        os.remove(CHECKPOINT_FILE)
    print("Done.")


if __name__ == "__main__":
    import sys
    test = "--test" in sys.argv
    main(test_mode=test)
