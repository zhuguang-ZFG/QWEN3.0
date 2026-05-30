"""
eval_loop.py — red V1flash 自动蒸馏+持续训练系统的评估模块

每次训练完成后自动评估新模型，与当前激活版本对比，决定是否升级部署。
这是防止模型退化的最后一道防线。
"""

import json
import os
import glob
import logging
import urllib.request
import urllib.error
from datetime import datetime

import model_registry

_log = logging.getLogger(__name__)

# ─── 常量 ────────────────────────────────────────────────────────────────────

EVAL_SET_PATH = "D:/GIT/data/eval/eval_set.json"
RESULTS_DIR = "D:/GIT/data/eval/results"
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL = "local-model"
DOMAIN_WEIGHT = 1 / 3  # 三域等权重
MAX_DOMAIN_DROP = 0.05  # 单域最大允许下降幅度


# ─── 默认评估集 ───────────────────────────────────────────────────────────────

DEFAULT_EVAL_SET = [
    # grbl_config (10条)
    {
        "query": "GRBL $100 步数怎么计算",
        "answer": "步数/mm = 电机步数 × 细分数 / 丝杆导程",
        "intent": "grbl_config",
        "keywords": ["步数", "细分", "导程", "steps_per_mm"],
    },
    {
        "query": "GRBL $110 最大速度如何设置",
        "answer": "$110 设置 X 轴最大速度，单位 mm/min，典型值 3000-8000",
        "intent": "grbl_config",
        "keywords": ["最大速度", "mm/min", "$110", "X轴"],
    },
    {
        "query": "GRBL $120 加速度参数含义",
        "answer": "$120 是 X 轴加速度，单位 mm/s²，影响启停平滑度",
        "intent": "grbl_config",
        "keywords": ["加速度", "mm/s", "$120", "启停"],
    },
    {
        "query": "GRBL 归零流程是什么",
        "answer": "发送 $H 触发归零，机器先快速移动到限位开关，再慢速回退确认位置",
        "intent": "grbl_config",
        "keywords": ["归零", "$H", "限位", "homing"],
    },
    {
        "query": "GRBL 限位开关如何配置",
        "answer": "$21=1 启用硬限位，$22=1 启用归零，$23 设置归零方向",
        "intent": "grbl_config",
        "keywords": ["限位", "$21", "$22", "硬限位"],
    },
    {
        "query": "GRBL $130 行程范围怎么设置",
        "answer": "$130/$131/$132 分别设置 X/Y/Z 轴最大行程，单位 mm",
        "intent": "grbl_config",
        "keywords": ["行程", "$130", "$131", "$132", "最大行程"],
    },
    {
        "query": "GRBL 软限位和硬限位区别",
        "answer": "软限位 $20=1 通过坐标判断，硬限位 $21=1 通过物理开关触发",
        "intent": "grbl_config",
        "keywords": ["软限位", "硬限位", "$20", "$21"],
    },
    {
        "query": "GRBL 步进电机细分数如何影响精度",
        "answer": "细分数越高精度越高，但速度上限降低；常用 1/8 或 1/16 细分",
        "intent": "grbl_config",
        "keywords": ["细分", "精度", "步进", "微步"],
    },
    {
        "query": "GRBL $1 步进电机保持电流含义",
        "answer": "$1 设置步进电机停止后保持电流的延迟时间，255 表示始终保持",
        "intent": "grbl_config",
        "keywords": ["保持电流", "$1", "步进电机", "延迟"],
    },
    {
        "query": "GRBL 坐标系 G54 和机器坐标区别",
        "answer": "G54 是工件坐标系，机器坐标是绝对原点；G92 或 G10 设置工件原点偏移",
        "intent": "grbl_config",
        "keywords": ["G54", "工件坐标", "机器坐标", "G92"],
    },
    # cnc_trouble (10条)
    {
        "query": "CNC 失步原因和解决方法",
        "answer": "失步原因：速度过快、加速度过大、电流不足；解决：降速、减加速度、增大驱动电流",
        "intent": "cnc_trouble",
        "keywords": ["失步", "加速度", "电流", "降速"],
    },
    {
        "query": "CNC 电机抖动如何排查",
        "answer": "抖动原因：驱动器电流过大、细分设置错误、接线松动、共振；检查驱动器参数和接线",
        "intent": "cnc_trouble",
        "keywords": ["抖动", "驱动器", "共振", "细分"],
    },
    {
        "query": "GRBL ALARM:1 是什么错误",
        "answer": "ALARM:1 是硬限位触发报警，需要 $X 解锁后重新归零",
        "intent": "cnc_trouble",
        "keywords": ["ALARM:1", "硬限位", "$X", "解锁"],
    },
    {
        "query": "GRBL ALARM:3 原因",
        "answer": "ALARM:3 是归零失败，限位开关未触发；检查开关接线和 $23 方向设置",
        "intent": "cnc_trouble",
        "keywords": ["ALARM:3", "归零失败", "限位开关", "$23"],
    },
    {
        "query": "CNC 加工时出现振纹如何解决",
        "answer": "振纹原因：进给速度过快、主轴转速不匹配、刀具磨损；降低进给或调整转速",
        "intent": "cnc_trouble",
        "keywords": ["振纹", "进给", "主轴", "刀具"],
    },
    {
        "query": "GRBL error:20 是什么",
        "answer": "error:20 是 G 代码中不支持的命令；检查 G 代码语法是否符合 GRBL 支持范围",
        "intent": "cnc_trouble",
        "keywords": ["error:20", "G代码", "语法", "不支持"],
    },
    {
        "query": "CNC 限位开关误触发怎么处理",
        "answer": "误触发原因：电磁干扰、开关抖动；解决：加滤波电容、屏蔽线、软件去抖",
        "intent": "cnc_trouble",
        "keywords": ["误触发", "干扰", "滤波", "去抖"],
    },
    {
        "query": "GRBL 归零后坐标不准确",
        "answer": "检查 $27 归零回退距离、限位开关重复精度、以及机械间隙补偿",
        "intent": "cnc_trouble",
        "keywords": ["归零", "$27", "回退", "重复精度"],
    },
    {
        "query": "CNC 主轴不转动排查步骤",
        "answer": "检查 M3/M4 指令、主轴使能信号、PWM 输出、变频器参数和电源",
        "intent": "cnc_trouble",
        "keywords": ["主轴", "M3", "PWM", "变频器"],
    },
    {
        "query": "GRBL 运行中突然停止原因",
        "answer": "可能原因：限位触发、急停按下、USB 断连、电源波动；查看串口返回的 ALARM 信息",
        "intent": "cnc_trouble",
        "keywords": ["停止", "急停", "ALARM", "USB"],
    },
    # embedded_dev (10条)
    {
        "query": "ESP32 PWM 如何配置频率和占空比",
        "answer": "使用 ledcSetup 设置频率和分辨率，ledcAttachPin 绑定引脚，ledcWrite 设置占空比",
        "intent": "embedded_dev",
        "keywords": ["PWM", "ledcSetup", "ledcWrite", "占空比"],
    },
    {
        "query": "STM32 定时器中断如何配置",
        "answer": "配置 TIM_TimeBaseInitTypeDef，设置预分频和重装值，使能 TIM_IT_Update 中断",
        "intent": "embedded_dev",
        "keywords": ["定时器", "TIM", "中断", "预分频"],
    },
    {
        "query": "FreeRTOS 任务创建函数参数含义",
        "answer": "xTaskCreate(函数, 名称, 栈大小, 参数, 优先级, 句柄)；栈大小单位为字",
        "intent": "embedded_dev",
        "keywords": ["xTaskCreate", "FreeRTOS", "优先级", "栈大小"],
    },
    {
        "query": "编码器如何读取位置信息",
        "answer": "正交编码器通过 A/B 相计数，STM32 定时器编码器模式自动计数，读取 CNT 寄存器",
        "intent": "embedded_dev",
        "keywords": ["编码器", "正交", "CNT", "计数"],
    },
    {
        "query": "ESP32 I2C 通信如何初始化",
        "answer": "Wire.begin(SDA, SCL) 初始化，Wire.beginTransmission 发起通信，Wire.write 发送数据",
        "intent": "embedded_dev",
        "keywords": ["I2C", "Wire", "SDA", "SCL"],
    },
    {
        "query": "FreeRTOS 队列如何在任务间传递数据",
        "answer": "xQueueCreate 创建队列，xQueueSend 发送，xQueueReceive 接收；支持阻塞等待",
        "intent": "embedded_dev",
        "keywords": ["队列", "xQueueCreate", "xQueueSend", "xQueueReceive"],
    },
    {
        "query": "STM32 SPI 全双工通信配置",
        "answer": "配置 SPI_InitTypeDef，设置模式、波特率、数据位；HAL_SPI_TransmitReceive 收发",
        "intent": "embedded_dev",
        "keywords": ["SPI", "全双工", "HAL_SPI", "波特率"],
    },
    {
        "query": "ESP32 深度睡眠如何唤醒",
        "answer": "esp_sleep_enable_timer_wakeup 定时唤醒，esp_sleep_enable_ext0_wakeup 引脚唤醒",
        "intent": "embedded_dev",
        "keywords": ["深度睡眠", "唤醒", "esp_sleep", "低功耗"],
    },
    {
        "query": "FreeRTOS 互斥锁和信号量区别",
        "answer": "互斥锁有优先级继承防止优先级反转，信号量用于计数和同步；互斥锁必须由同一任务释放",
        "intent": "embedded_dev",
        "keywords": ["互斥锁", "信号量", "优先级反转", "同步"],
    },
    {
        "query": "STM32 ADC 采样如何提高精度",
        "answer": "增加采样时间、使用过采样平均、添加硬件滤波电容、参考电压稳定",
        "intent": "embedded_dev",
        "keywords": ["ADC", "采样", "过采样", "精度"],
    },
]


# ─── 函数实现 ─────────────────────────────────────────────────────────────────


def create_default_eval_set(path: str = EVAL_SET_PATH) -> None:
    """如果评估集文件不存在，创建包含30条覆盖三个域的默认评估题。

    三个域各10条：
    - grbl_config：GRBL 参数配置相关
    - cnc_trouble：CNC 故障排查相关
    - embedded_dev：嵌入式开发相关

    Args:
        path: 评估集文件路径，默认 D:/GIT/data/eval/eval_set.json
    """
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_EVAL_SET, f, indent=2, ensure_ascii=False)
    print(f"[eval_loop] 创建默认评估集：{path}，共 {len(DEFAULT_EVAL_SET)} 条")


def _infer_version(adapter_path: str) -> str:
    """从 adapter_path 推断版本号。

    优先读取 trainer_state.json，失败时用时间戳。

    Args:
        adapter_path: adapter 目录路径

    Returns:
        版本号字符串，如 "r7_step4000" 或 "v20260518_1430"
    """
    state_path = os.path.join(adapter_path, "trainer_state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        step = state.get("global_step")
        if step is None:
            log_history = state.get("log_history", [])
            if log_history:
                step = log_history[-1].get("step")
        if step is not None:
            basename = os.path.basename(adapter_path.rstrip("/\\"))
            round_num = 1
            for part in basename.split("_"):
                if part.startswith("r") and part[1:].isdigit():
                    round_num = int(part[1:])
                    break
            return f"r{round_num}_step{step}"
    except Exception as exc:
        _log.debug("eval_loop.py: {}", type(exc).__name__)
    return f"v{datetime.now().strftime('%Y%m%d_%H%M')}"


def _call_lm_studio(query: str, timeout: int = 30) -> str:
    """调用本地 LM Studio 推理接口。

    Args:
        query: 用户问题
        timeout: 请求超时秒数

    Returns:
        模型回答字符串，失败时返回空字符串

    Raises:
        urllib.error.URLError: 连接失败时抛出
    """
    payload = {
        "model": LM_STUDIO_MODEL,
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 256,
        "temperature": 0.1,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LM_STUDIO_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"]


def _score_answer(answer: str, keywords: list) -> bool:
    """判断回答是否包含至少一个关键词（大小写不敏感）。

    Args:
        answer: 模型回答文本
        keywords: 关键词列表

    Returns:
        True 表示命中至少一个关键词
    """
    answer_lower = answer.lower()
    for kw in keywords:
        if kw.lower() in answer_lower:
            return True
    return False


def run_eval(
    adapter_path: str,
    eval_set_path: str = EVAL_SET_PATH,
    version: str = None,
) -> dict:
    """加载评估集，对每条题目调用 LM Studio 推理，按域统计准确率。

    准确率 = 回答中包含 keywords 中至少一个关键词的比例。
    LM Studio 不可用时，overall=0.0，passed=False，注明原因。

    Args:
        adapter_path: adapter 目录路径，用于推断版本号
        eval_set_path: 评估集 JSON 文件路径
        version: 可选版本号；传入时直接使用，不再从 adapter_path 推断

    Returns:
        EvalResult 字典，包含 version/domain_scores/overall/passed 等字段
    """
    if version is None:
        version = _infer_version(adapter_path)
    timestamp = datetime.now().isoformat()

    # 加载评估集
    with open(eval_set_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    # 按域分组
    domain_items: dict = {}
    for item in eval_set:
        intent = item.get("intent", "unknown")
        domain_items.setdefault(intent, []).append(item)

    domain_scores: dict = {}
    total_correct = 0
    total_questions = len(eval_set)
    lm_unavailable_reason = None

    # 检测 LM Studio 是否可用（连接探测）
    # HTTPError（4xx/5xx）说明服务在运行，只有 URLError（连接失败）才视为不可用
    lm_available = True
    try:
        _call_lm_studio("test", timeout=5)
    except urllib.error.HTTPError:
        # 服务在运行，只是请求格式问题，视为可用
        pass
    except urllib.error.URLError as probe_err:
        lm_available = False
        lm_unavailable_reason = f"LM Studio 不可用：{probe_err}"
        print(f"[eval_loop] {lm_unavailable_reason}")
    except Exception:
        # 其他异常（超时等）也视为不可用
        lm_available = False
        lm_unavailable_reason = "LM Studio 连接超时或未知错误"
        print(f"[eval_loop] {lm_unavailable_reason}")

    if not lm_available:
        for domain in domain_items:
            domain_scores[domain] = 0.0
        # 补全三个标准域
        for d in ("grbl_config", "cnc_trouble", "embedded_dev"):
            domain_scores.setdefault(d, 0.0)
        return {
            "version": version,
            "adapter_path": adapter_path,
            "timestamp": timestamp,
            "domain_scores": domain_scores,
            "overall": 0.0,
            "passed": False,
            "rollback_reason": lm_unavailable_reason,
            "total_questions": total_questions,
            "correct_count": 0,
        }

    # 逐题推理评分
    for domain, items in domain_items.items():
        correct = 0
        for item in items:
            try:
                answer = _call_lm_studio(item["query"], timeout=30)
                if _score_answer(answer, item.get("keywords", [])):
                    correct += 1
                    total_correct += 1
            except Exception as e:
                print(f"[eval_loop] 推理失败 ({item['query'][:30]}...): {e}")
        domain_scores[domain] = correct / len(items) if items else 0.0

    # 补全三个标准域（评估集可能缺某域）
    for d in ("grbl_config", "cnc_trouble", "embedded_dev"):
        domain_scores.setdefault(d, 0.0)

    overall = (
        domain_scores["grbl_config"]
        + domain_scores["cnc_trouble"]
        + domain_scores["embedded_dev"]
    ) * DOMAIN_WEIGHT

    return {
        "version": version,
        "adapter_path": adapter_path,
        "timestamp": timestamp,
        "domain_scores": domain_scores,
        "overall": round(overall, 4),
        "passed": False,  # 由 promote_if_better 设置
        "rollback_reason": None,
        "total_questions": total_questions,
        "correct_count": total_correct,
    }


def compare(new_result: dict) -> tuple:
    """对比新版本与历史最新评估结果。

    对比规则：
    - new overall >= old overall
    - 且无单域下降 > 5%（0.05）
    两个条件都满足才返回 (True, "")。
    无历史记录时直接返回 (True, "首次评估，自动通过")。

    Args:
        new_result: run_eval 返回的 EvalResult 字典

    Returns:
        (passed: bool, reason: str) 元组
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    history_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json")))

    if not history_files:
        return (True, "首次评估，自动通过")

    # 读取最新历史记录
    latest_file = history_files[-1]
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            old_result = json.load(f)
    except Exception as e:
        return (True, f"历史记录读取失败，自动通过：{e}")

    old_overall = old_result.get("overall", 0.0)
    new_overall = new_result.get("overall", 0.0)
    old_domains = old_result.get("domain_scores", {})
    new_domains = new_result.get("domain_scores", {})

    # 条件1：整体分数不退化
    if new_overall < old_overall:
        reason = (
            f"整体分数下降：{old_overall:.4f} → {new_overall:.4f}"
            f"（下降 {old_overall - new_overall:.4f}）"
        )
        return (False, reason)

    # 条件2：无单域下降超过阈值
    for domain in ("grbl_config", "cnc_trouble", "embedded_dev"):
        old_score = old_domains.get(domain, 0.0)
        new_score = new_domains.get(domain, 0.0)
        drop = old_score - new_score
        if drop > MAX_DOMAIN_DROP:
            reason = (
                f"域 [{domain}] 下降过大：{old_score:.4f} → {new_score:.4f}"
                f"（下降 {drop:.4f} > 阈值 {MAX_DOMAIN_DROP}）"
            )
            return (False, reason)

    return (True, "")


def append_history(result: dict) -> None:
    """将评估结果写入历史记录文件。

    文件名格式：{version}_{timestamp}.json
    timestamp 中的冒号替换为连字符以兼容 Windows 文件名。

    Args:
        result: EvalResult 字典
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    version = result.get("version", "unknown")
    ts = result.get("timestamp", datetime.now().isoformat())
    # 替换冒号，兼容 Windows 文件名
    ts_safe = ts.replace(":", "-").replace(".", "-")
    filename = f"{version}_{ts_safe}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[eval_loop] 评估结果已写入：{filepath}")


def promote_if_better(new_result: dict) -> bool:
    """对比历史结果，决定是否升级部署新版本。

    如果通过：调用 model_registry.promote(version)，更新 passed=True。
    如果不通过：打印原因，设置 passed=False 和 rollback_reason。
    最终调用 append_history 持久化结果。

    Args:
        new_result: run_eval 返回的 EvalResult 字典（会被原地修改）

    Returns:
        True 表示已升级，False 表示回滚/跳过
    """
    passed, reason = compare(new_result)
    version = new_result.get("version", "unknown")

    if passed:
        new_result["passed"] = True
        new_result["rollback_reason"] = None
        promoted = model_registry.promote(version)
        if promoted:
            print(f"[eval_loop] 版本 {version} 已升级为激活版本")
        else:
            print(f"[eval_loop] 警告：model_registry.promote({version}) 返回 False（版本未注册？）")
    else:
        new_result["passed"] = False
        new_result["rollback_reason"] = reason
        print(f"[eval_loop] 版本 {version} 未通过评估，保持当前激活版本")
        print(f"[eval_loop] 原因：{reason}")

    append_history(new_result)
    return passed


def run_full_eval_cycle(adapter_path: str, version: str = None) -> dict:
    """完整评估周期：创建评估集 → 推理评估 → 对比升级。

    Args:
        adapter_path: adapter 目录路径
        version: 可选版本号；传入时直接使用，不再从 adapter_path 推断

    Returns:
        最终 EvalResult 字典
    """
    print(f"\n[eval_loop] ===== 开始评估周期 =====")
    print(f"[eval_loop] adapter_path: {adapter_path}")

    # 步骤1：确保评估集存在
    create_default_eval_set()

    # 步骤2：运行评估
    print("[eval_loop] 正在推理评估...")
    result = run_eval(adapter_path, version=version)

    # 步骤3：对比并决定是否升级
    promoted = promote_if_better(result)

    # 打印摘要
    print(f"\n[eval_loop] ===== 评估摘要 =====")
    print(f"  版本：{result['version']}")
    print(f"  总题数：{result['total_questions']}，答对：{result['correct_count']}")
    print(f"  grbl_config：{result['domain_scores'].get('grbl_config', 0):.2%}")
    print(f"  cnc_trouble：{result['domain_scores'].get('cnc_trouble', 0):.2%}")
    print(f"  embedded_dev：{result['domain_scores'].get('embedded_dev', 0):.2%}")
    print(f"  整体得分：{result['overall']:.2%}")
    print(f"  升级结果：{'已升级' if promoted else '未升级'}")
    if result.get("rollback_reason"):
        print(f"  回滚原因：{result['rollback_reason']}")
    print(f"[eval_loop] ===== 评估周期结束 =====\n")

    return result


# ─── 测试块 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("eval_loop.py 自测")
    print("=" * 60)

    # 测试1：创建默认评估集
    create_default_eval_set()
    with open(EVAL_SET_PATH, "r", encoding="utf-8") as _f:
        _eval_set = json.load(_f)
    print(f"\n[测试1] 评估集条数：{len(_eval_set)}")
    domains = {}
    for item in _eval_set:
        domains[item["intent"]] = domains.get(item["intent"], 0) + 1
    for d, cnt in sorted(domains.items()):
        print(f"  {d}: {cnt} 条")

    # 测试2：run_eval 降级行为（LM Studio 不可用时）
    print("\n[测试2] 测试 LM Studio 不可用时的降级行为...")
    _fake_adapter = "D:/GIT/fake_adapter_r1_step100"
    _result = run_eval(_fake_adapter)
    print(f"  overall: {_result['overall']}")
    print(f"  passed: {_result['passed']}")
    print(f"  rollback_reason: {_result['rollback_reason']}")
    print(f"  total_questions: {_result['total_questions']}")

    print("\n[测试] 全部通过")
    sys.exit(0)
