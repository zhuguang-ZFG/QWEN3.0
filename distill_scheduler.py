#!/usr/bin/env python3
"""distill_scheduler.py — GPU 空闲检测 + Superpower 教师模型并发蒸馏调度器

LiMa 自动蒸馏+持续训练系统的核心调度模块。
GPU 空闲时，从题库取题，并发调用多个 AI API（Superpower 原则：
代码题用 Qwen Coder 480B，故障诊断用 DeepSeek PRO，嵌入式用 Nvidia Nemotron），
生成高质量 Q&A 对，写入待质检目录。
"""

import json
import os
import re
import uuid
import time
import subprocess
import concurrent.futures
import urllib.request
import urllib.error
from datetime import datetime, date
from dotenv import load_dotenv
import quota_tracker

load_dotenv()

# ---------------------------------------------------------------------------
# Superpower 教师模型映射（意图 -> 最强教师后端列表）
# 免费优先原则：L1=LongCat/中国移动免费 | L2=Nvidia免费额度 | L3=OpenRouter免费额度
# ---------------------------------------------------------------------------
TEACHER_MAP = {
    "cnc_trouble":     ["longcat_thinking", "nvidia_nemotron", "or_deepseek_r1"],
    "grbl_config":     ["longcat", "nvidia_llama70b", "or_llama70b"],
    "gcode_help":      ["longcat_chat", "nvidia_llama4", "or_llama70b"],
    "embedded_dev":    ["nvidia_nemotron", "longcat_thinking", "or_nemotron"],
    "code_generation": ["nvidia_qwen_coder", "or_qwen3_coder", "longcat_chat"],
    "complex_theory":  ["longcat_thinking", "nvidia_nemotron", "or_deepseek_r1"],
    "general_cnc":     ["longcat_lite", "chinamobile", "nvidia_llama4"],
    "unknown":         ["longcat_chat", "nvidia_llama70b", "or_llama70b"],
}

# ---------------------------------------------------------------------------
# API 后端配置（内置，不 import smart_router，避免循环依赖）
# ---------------------------------------------------------------------------
BACKEND_CONFIGS = {
    "deepseek_pro":     {"url": "https://api.deepseek.com/anthropic/v1/messages",
                         "model": "deepseek-v4-pro", "fmt": "anthropic",
                         "key_env": "DEEPSEEK_API_KEY"},
    "deepseek_flash":   {"url": "https://api.deepseek.com/anthropic/v1/messages",
                         "model": "deepseek-v4-flash", "fmt": "anthropic",
                         "key_env": "DEEPSEEK_API_KEY"},
    "claude":           {"url": "https://right.codes/claude-aws/v1/messages",
                         "model": "claude-sonnet-4-6", "fmt": "anthropic",
                         "key_env": "CLAUDE_API_KEY"},
    "nvidia_nemotron":  {"url": "https://integrate.api.nvidia.com/v1/chat/completions",
                         "model": "nvidia/llama-3.3-nemotron-super-49b-v1", "fmt": "openai",
                         "key_env": "NVIDIA_API_KEY"},
    "nvidia_qwen_coder":{"url": "https://integrate.api.nvidia.com/v1/chat/completions",
                         "model": "qwen/qwen3-coder-480b-a35b-instruct", "fmt": "openai",
                         "key_env": "NVIDIA_API_KEY"},
    "nvidia_llama70b":  {"url": "https://integrate.api.nvidia.com/v1/chat/completions",
                         "model": "meta/llama-3.3-70b-instruct", "fmt": "openai",
                         "key_env": "NVIDIA_API_KEY"},
    "longcat":          {"url": "https://api.longcat.chat/anthropic/v1/messages",
                         "model": "LongCat-2.0-Preview", "fmt": "anthropic",
                         "key_env": "LONGCAT_API_KEY"},
    "longcat_chat":     {"url": "https://api.longcat.chat/anthropic/v1/messages",
                         "model": "LongCat-Flash-Chat", "fmt": "anthropic",
                         "key_env": "LONGCAT_API_KEY"},
    "chinamobile":      {"url": "https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1/chat/completions",
                         "model": "minimax-m25", "fmt": "openai",
                         "key_env": "CHINAMOBILE_API_KEY"},
}

SYS_PROMPT = (
    "你是CNC/嵌入式领域专家。给出详细、准确的中文技术回答，"
    "包含具体参数、代码示例和操作步骤。不要免责声明。"
)

# ---------------------------------------------------------------------------
# 合成题模板（至少14条）
# ---------------------------------------------------------------------------
SYNTHETIC_TEMPLATES = [
    "GRBL $100 步数怎么计算",
    "步进电机失步怎么排查",
    "ESP32 PWM 频率怎么设置",
    "G2 圆弧插补 IJK 参数说明",
    "主轴转速 M3 S1000 不转怎么办",
    "限位开关触发后归零失败",
    "STM32 定时器中断配置",
    "CNC 雕刻机 Z 轴抖动",
    "GRBL alarm:1 怎么解除",
    "FreeRTOS 任务优先级设置",
    "编码器反馈闭环控制",
    "激光雕刻功率设置",
    "G92 坐标系偏移用法",
    "步进驱动器细分设置",
]

# ---------------------------------------------------------------------------
# 意图分类规则（简化版，不 import smart_router）
# ---------------------------------------------------------------------------
_INTENT_RULES = [
    ("code_generation", re.compile(
        r'代码|编程|程序|函数|实现|写.*?代码|ESP32|STM32|Arduino|FreeRTOS|HAL_|'
        r'#include|void\s+\w+|int\s+main', re.I)),
    ("grbl_config",     re.compile(
        r'\$\d+|GRBL|grbl|步数|steps.*?mm|mm.*?steps|归零|homing|\$H|\$X', re.I)),
    # cnc_trouble 在 gcode_help 之前，避免 M3/G 指令掩盖故障关键词
    ("cnc_trouble",     re.compile(
        r'故障|报警|alarm|error|失步|抖动|不转|不动|卡顿|异常|排查|诊断', re.I)),
    ("gcode_help",      re.compile(
        r'G\d+|M\d+|G-?code|gcode|圆弧|插补|坐标系|G92|G28|G0|G1|G2|G3', re.I)),
    ("embedded_dev",    re.compile(
        r'嵌入式|单片机|MCU|RTOS|中断|PWM|SPI|I2C|UART|DMA|寄存器|固件', re.I)),
    ("complex_theory",  re.compile(
        r'原理|理论|算法|PID|闭环|开环|伺服|控制论|插补算法|运动规划', re.I)),
    ("general_cnc",     re.compile(
        r'CNC|数控|雕刻机|激光|主轴|进给|切削|刀具|工件|加工', re.I)),
]


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------

def _classify_intent(query: str) -> str:
    """根据关键词规则对查询进行意图分类。

    Args:
        query: 用户查询字符串。

    Returns:
        意图字符串，如 'cnc_trouble'、'code_generation' 等，
        无匹配时返回 'unknown'。
    """
    for intent, pattern in _INTENT_RULES:
        if pattern.search(query):
            return intent
    return "unknown"


def check_gpu_idle(
    util_threshold: int = 30,
    mem_threshold_gb: float = 4.0,
    window_minutes: int = 5,
) -> bool:
    """调用 nvidia-smi 检测 GPU 是否空闲。

    采样一次 GPU 利用率和显存占用，判断是否满足空闲条件。
    nvidia-smi 不可用时返回 True（假设空闲，允许蒸馏）。

    Args:
        util_threshold:    GPU 利用率阈值（%），低于此值视为空闲。
        mem_threshold_gb:  显存占用阈值（GB），低于此值视为空闲。
        window_minutes:    保留参数，当前实现不做滑动窗口。

    Returns:
        True 表示 GPU 空闲，False 表示 GPU 繁忙。
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print("[distill] nvidia-smi 返回非零，假设 GPU 空闲")
            return True

        line = result.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        util_pct = float(parts[0])
        mem_used_mb = float(parts[1])
        mem_used_gb = mem_used_mb / 1024.0

        idle = util_pct < util_threshold and mem_used_gb < mem_threshold_gb
        print(
            f"[distill] GPU util={util_pct:.1f}% mem={mem_used_gb:.2f}GB "
            f"-> {'空闲' if idle else '繁忙'}"
        )
        return idle

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
        print(f"[distill] nvidia-smi 不可用 ({exc})，假设 GPU 空闲")
        return True


def build_job_queue(max_jobs: int = 50) -> list:
    """构建优先级蒸馏任务队列。

    优先级策略：
      1. D:/GIT/data/distill_queue/pending/ 下的用户日志 .json（priority=1.0）
      2. D:/GIT/data/training_data/ 下随机采样问题（priority=0.6）
      3. 合成题（priority=0.3）

    Args:
        max_jobs: 最大任务数，默认 50。

    Returns:
        按 priority 降序排列的 DistillJob 字典列表。
    """
    import random
    import glob

    jobs = []

    # --- 1. 用户日志（priority=1.0）---
    pending_dir = "D:/GIT/data/distill_queue/pending/"
    if os.path.isdir(pending_dir):
        for fpath in glob.glob(os.path.join(pending_dir, "*.json")):
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
                query = data.get("query") or data.get("question") or ""
                if not query:
                    continue
                intent = _classify_intent(query)
                jobs.append({
                    "job_id":          str(uuid.uuid4()),
                    "query":           query,
                    "intent":          intent,
                    "priority":        1.0,
                    "source":          "user_log",
                    "teacher_backends": TEACHER_MAP.get(intent, TEACHER_MAP["unknown"]),
                    "status":          "pending",
                    "created_at":      datetime.utcnow().isoformat(),
                })
                if len(jobs) >= max_jobs:
                    break
            except Exception as exc:
                print(f"[distill] 跳过 {fpath}: {exc}")

    # --- 2. 训练数据随机采样（priority=0.6）---
    if len(jobs) < max_jobs:
        training_dir = "D:/GIT/data/training_data/"
        training_files = []
        if os.path.isdir(training_dir):
            training_files = glob.glob(os.path.join(training_dir, "**/*.json"),
                                       recursive=True)
        random.shuffle(training_files)
        for fpath in training_files:
            if len(jobs) >= max_jobs:
                break
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
                # 支持列表或单条
                records = data if isinstance(data, list) else [data]
                for rec in records:
                    if len(jobs) >= max_jobs:
                        break
                    query = rec.get("query") or rec.get("question") or ""
                    if not query:
                        continue
                    intent = _classify_intent(query)
                    jobs.append({
                        "job_id":          str(uuid.uuid4()),
                        "query":           query,
                        "intent":          intent,
                        "priority":        0.6,
                        "source":          "training_data",
                        "teacher_backends": TEACHER_MAP.get(intent, TEACHER_MAP["unknown"]),
                        "status":          "pending",
                        "created_at":      datetime.utcnow().isoformat(),
                    })
            except Exception as exc:
                print(f"[distill] 跳过 {fpath}: {exc}")

    # --- 3. 合成题（priority=0.3）---
    if len(jobs) < max_jobs:
        import random as _rnd
        templates = list(SYNTHETIC_TEMPLATES)
        _rnd.shuffle(templates)
        for tmpl in templates:
            if len(jobs) >= max_jobs:
                break
            intent = _classify_intent(tmpl)
            jobs.append({
                "job_id":          str(uuid.uuid4()),
                "query":           tmpl,
                "intent":          intent,
                "priority":        0.3,
                "source":          "synthetic",
                "teacher_backends": TEACHER_MAP.get(intent, TEACHER_MAP["unknown"]),
                "status":          "pending",
                "created_at":      datetime.utcnow().isoformat(),
            })

    # 按 priority 降序，取前 max_jobs 条
    jobs.sort(key=lambda j: j["priority"], reverse=True)
    return jobs[:max_jobs]


def _call_teacher(backend_name: str, query: str, max_tokens: int = 800) -> str | None:
    """调用指定教师模型后端，返回回答文本。

    直接使用 urllib.request，不 import smart_router，避免循环依赖。
    支持 anthropic 和 openai 两种 API 格式。

    Args:
        backend_name: BACKEND_CONFIGS 中的后端名称。
        query:        用户查询字符串。
        max_tokens:   最大生成 token 数，默认 800。

    Returns:
        模型回答字符串，失败时返回 None。
    """
    cfg = BACKEND_CONFIGS.get(backend_name)
    if not cfg:
        print(f"[distill] 未知后端: {backend_name}")
        return None

    # 配额检查：超限时自动降级到免费后端
    actual_backend = backend_name
    if not quota_tracker.check_quota(backend_name):
        fallback = quota_tracker.get_fallback(backend_name)
        print(f"[distill] {backend_name} 配额超限，降级到 {fallback}")
        actual_backend = fallback
        cfg = BACKEND_CONFIGS.get(actual_backend)
        if not cfg:
            print(f"[distill] 降级后端 {actual_backend} 未配置，跳过")
            return None

    api_key = os.environ.get(cfg["key_env"], "")
    if not api_key:
        print(f"[distill] {backend_name} 缺少 API key ({cfg['key_env']})")
        return None

    url = cfg["url"]
    fmt = cfg["fmt"]
    model = cfg["model"]

    try:
        if fmt == "anthropic":
            payload = {
                "model":      model,
                "max_tokens": max_tokens,
                "system":     SYS_PROMPT,
                "messages":   [{"role": "user", "content": query}],
            }
            headers = {
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            }
        else:  # openai
            payload = {
                "model":      model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": SYS_PROMPT},
                    {"role": "user",   "content": query},
                ],
            }
            headers = {
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_key}",
            }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        if fmt == "anthropic":
            result_text = body["content"][0]["text"]
        else:
            result_text = body["choices"][0]["message"]["content"]

        # 调用成功，记录配额
        quota_tracker.record_call(actual_backend)
        return result_text

    except urllib.error.HTTPError as exc:
        print(f"[distill] {backend_name} HTTP {exc.code}: {exc.reason}")
        return None
    except Exception as exc:
        print(f"[distill] {backend_name} 调用失败: {exc}")
        return None


def _process_job(job: dict) -> dict | None:
    """处理单个蒸馏任务，并发调用所有教师后端。

    Args:
        job: DistillJob 字典。

    Returns:
        QAPair 字典，所有后端均失败时返回 None。
    """
    query = job["query"]
    backends = job["teacher_backends"]
    all_answers = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(backends)) as inner:
        future_map = {
            inner.submit(_call_teacher, b, query): b
            for b in backends
        }
        for fut in concurrent.futures.as_completed(future_map):
            bname = future_map[fut]
            try:
                answer = fut.result()
                if answer:
                    all_answers[bname] = answer
            except Exception as exc:
                print(f"[distill] job {job['job_id'][:8]} {bname} 异常: {exc}")

    if not all_answers:
        return None

    # 选主回答：取第一个成功的后端
    primary_backend = next(
        (b for b in backends if b in all_answers), list(all_answers.keys())[0]
    )

    return {
        "job_id":          job["job_id"],
        "query":           query,
        "answer":          all_answers[primary_backend],
        "intent":          job["intent"],
        "source":          job["source"],
        "source_backend":  primary_backend,
        "teacher_backends": backends,
        "all_answers":     list(all_answers.values()) if isinstance(all_answers, dict) else all_answers,
        "priority":        job["priority"],
        "created_at":      job["created_at"],
        "distilled_at":    datetime.utcnow().isoformat(),
    }


def run_batch(jobs: list, concurrency: int = 3) -> list:
    """并发调用教师模型，批量生成 QAPair。

    每个 job 并发调用 teacher_backends 中的3个后端，
    收集所有回答，构建 QAPair 字典列表。

    Args:
        jobs:        DistillJob 字典列表。
        concurrency: 并发 job 数，默认 3。

    Returns:
        QAPair 字典列表（跳过所有后端均失败的 job）。
    """
    qa_pairs = []
    total = len(jobs)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(_process_job, job): job for job in jobs}
        done_count = 0
        for fut in concurrent.futures.as_completed(future_map):
            done_count += 1
            job = future_map[fut]
            try:
                result = fut.result()
                if result:
                    qa_pairs.append(result)
                    print(
                        f"[distill] [{done_count}/{total}] "
                        f"job {job['job_id'][:8]} 完成 "
                        f"({len(result['all_answers'])} 个回答)"
                    )
                else:
                    print(
                        f"[distill] [{done_count}/{total}] "
                        f"job {job['job_id'][:8]} 所有后端失败，跳过"
                    )
            except Exception as exc:
                print(f"[distill] job {job['job_id'][:8]} 处理异常: {exc}")

    return qa_pairs


def save_pending(
    qa_pairs: list,
    out_dir: str = "D:/GIT/data/distill_queue/completed/",
) -> int:
    """将 QAPair 列表写入 JSON 文件。

    文件名格式：{date}_{uuid8}.json
    每次调用写入一个文件，包含本批次所有 QAPair。

    Args:
        qa_pairs: QAPair 字典列表。
        out_dir:  输出目录，默认 D:/GIT/data/distill_queue/completed/。

    Returns:
        写入条数。
    """
    if not qa_pairs:
        return 0

    os.makedirs(out_dir, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    uid8 = str(uuid.uuid4())[:8]
    filename = f"{today}_{uid8}.json"
    fpath = os.path.join(out_dir, filename)

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(qa_pairs, f, ensure_ascii=False, indent=2)

    print(f"[distill] 写入 {len(qa_pairs)} 条 -> {fpath}")
    return len(qa_pairs)


def run_idle_loop(interval_seconds: int = 60, batch_size: int = 20) -> None:
    """主循环：GPU 空闲时触发蒸馏批次。

    每 interval_seconds 秒检查 GPU 空闲状态，
    空闲则执行：build_job_queue -> run_batch -> save_pending。
    Ctrl+C 优雅退出。

    Args:
        interval_seconds: 检查间隔秒数，默认 60。
        batch_size:       每批次最大任务数，默认 20。
    """
    print("[distill] 启动空闲蒸馏循环，按 Ctrl+C 退出")
    try:
        while True:
            print(f"\n[distill] {datetime.now().strftime('%H:%M:%S')} 检查 GPU 状态...")
            if check_gpu_idle():
                print(f"[distill] GPU 空闲，构建 {batch_size} 条任务队列")
                jobs = build_job_queue(max_jobs=batch_size)
                print(f"[distill] 队列构建完成：{len(jobs)} 条任务")
                if jobs:
                    qa_pairs = run_batch(jobs)
                    saved = save_pending(qa_pairs)
                    print(f"[distill] 本批次完成：{saved} 条 QAPair 写入")
                else:
                    print("[distill] 队列为空，跳过本批次")
            else:
                print("[distill] GPU 繁忙，等待下次检查")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[distill] 收到 Ctrl+C，优雅退出")


# ---------------------------------------------------------------------------
# 测试块（不实际调用 API）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("distill_scheduler.py 测试块")
    print("=" * 60)

    print("\n[TEST] build_job_queue(max_jobs=5)")
    test_jobs = build_job_queue(max_jobs=5)
    for i, job in enumerate(test_jobs, 1):
        print(
            f"  [{i}] job_id={job['job_id'][:8]} "
            f"priority={job['priority']} "
            f"source={job['source']}\n"
            f"       intent={job['intent']}\n"
            f"       query={job['query'][:60]}\n"
            f"       teachers={job['teacher_backends']}"
        )

    print(f"\n[TEST] 共 {len(test_jobs)} 条任务，测试通过")
    print("\n[TEST] check_gpu_idle() 测试（不依赖真实 GPU）")
    result = check_gpu_idle()
    print(f"  GPU 空闲: {result}")
    print("\n[TEST] _classify_intent 测试")
    test_queries = [
        ("GRBL $100 步数怎么计算", "grbl_config"),
        ("ESP32 PWM 频率怎么设置", "code_generation"),
        ("主轴转速 M3 S1000 不转怎么办", "cnc_trouble"),
        ("G2 圆弧插补 IJK 参数说明", "gcode_help"),
    ]
    for q, expected in test_queries:
        got = _classify_intent(q)
        status = "OK" if got == expected else f"MISMATCH(expected={expected})"
        print(f"  {status}: '{q[:30]}' -> {got}")
    print("\n所有测试完成")
