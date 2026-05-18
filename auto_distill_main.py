#!/usr/bin/env python3
"""auto_distill_main.py — LiMa 自动蒸馏+持续训练系统主控守护进程

协调 quality_gate、model_registry、distill_scheduler、auto_trainer、eval_loop
五个模块，按状态机驱动全流程自动运行。

状态机流转：
  IDLE → (GPU空闲) → DISTILLING → (批次完成) → FILTERING
       → (积累达标) → TRAINING → (完成) → EVALUATING
       → (通过) → DEPLOYING → IDLE
       → (失败) → IDLE
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

import distill_scheduler
import quality_gate
import auto_trainer
import model_registry

# eval_loop 可能尚未实现完整接口，延迟导入并做防御
try:
    import eval_loop as _eval_loop_mod
    _EVAL_LOOP_AVAILABLE = hasattr(_eval_loop_mod, "run_full_eval_cycle")
except ImportError:
    _eval_loop_mod = None
    _EVAL_LOOP_AVAILABLE = False

# ─── 路径常量 ─────────────────────────────────────────────────────────────────

STATE_PATH = "D:/GIT/data/system_state.json"
HEARTBEAT_PATH = "D:/GIT/data/heartbeat.txt"

# ─── 合法阶段集合 ─────────────────────────────────────────────────────────────

PHASES = {"IDLE", "DISTILLING", "FILTERING", "TRAINING", "EVALUATING", "DEPLOYING"}


# ─── 状态持久化 ───────────────────────────────────────────────────────────────

def _initial_state() -> dict:
    """返回系统初始状态字典（phase=IDLE，所有计数归零）。"""
    return {
        "phase": "IDLE",
        "phase_entered_at": datetime.now().isoformat(),
        "distill_count_today": 0,
        "pending_quality_count": 0,
        "train_pool_count": 0,
        "last_train_at": None,
        "last_eval_at": None,
        "error_count": 0,
        "paused_until": None,
    }


def load_state() -> dict:
    """读取 system_state.json；文件不存在或损坏时返回初始状态。

    Returns:
        系统状态字典。
    """
    if not os.path.exists(STATE_PATH):
        return _initial_state()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 补全缺失字段（向前兼容）
        defaults = _initial_state()
        for key, val in defaults.items():
            data.setdefault(key, val)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[load_state] 读取状态文件失败，使用初始状态：{exc}")
        return _initial_state()


def save_state(state: dict) -> None:
    """将状态字典持久化到 system_state.json。

    Args:
        state: 系统状态字典。
    """
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def transition(state: dict, new_phase: str) -> dict:
    """更新 phase 和 phase_entered_at，打印转换日志，返回新状态（不可变风格）。

    Args:
        state:     当前状态字典。
        new_phase: 目标阶段名称，必须在 PHASES 中。

    Returns:
        更新后的新状态字典。
    """
    if new_phase not in PHASES:
        raise ValueError(f"非法阶段：{new_phase}")
    now_str = datetime.now().isoformat()
    old_phase = state.get("phase", "?")
    new_state = dict(state)
    new_state["phase"] = new_phase
    new_state["phase_entered_at"] = now_str
    print(f"[transition] {old_phase} → {new_phase}  ({now_str})")
    return new_state


# ─── 阶段处理函数 ─────────────────────────────────────────────────────────────

def run_distill_phase(state: dict) -> dict:
    """执行蒸馏阶段：检测 GPU 空闲后构建任务队列并并发蒸馏。

    流程：
      1. check_gpu_idle() — 不空闲则保持 IDLE 返回
      2. build_job_queue(max_jobs=20)
      3. run_batch(concurrency=3)
      4. save_pending()
      5. 更新 distill_count_today，转换到 FILTERING

    Args:
        state: 当前状态字典。

    Returns:
        更新后的状态字典。
    """
    new_state = dict(state)

    idle = distill_scheduler.check_gpu_idle()
    if not idle:
        print("[distill] GPU 繁忙，跳过本轮蒸馏")
        return new_state

    print("[distill] GPU 空闲，开始构建任务队列")
    jobs = distill_scheduler.build_job_queue(max_jobs=20)
    print(f"[distill] 任务队列：{len(jobs)} 条")

    results = distill_scheduler.run_batch(jobs, concurrency=3)
    saved = distill_scheduler.save_pending(results)
    count = len(saved) if isinstance(saved, list) else (saved or 0)

    new_state["distill_count_today"] = new_state.get("distill_count_today", 0) + count
    new_state["pending_quality_count"] = new_state.get("pending_quality_count", 0) + count
    print(f"[distill] 本批写入待质检：{count} 条，今日累计：{new_state['distill_count_today']}")

    return transition(new_state, "FILTERING")


def run_filter_phase(state: dict) -> dict:
    """执行过滤阶段：对待质检目录运行质量门控，通过样本写入训练池。

    Args:
        state: 当前状态字典。

    Returns:
        更新后的状态字典（转换到 IDLE 等待积累）。
    """
    new_state = dict(state)

    stats = quality_gate.process_pending_dir()
    total = stats.get("total", 0)
    passed = stats.get("passed", 0)
    rej_dedup = stats.get("rejected_dedup", 0)
    rej_qual = stats.get("rejected_quality", 0)

    print(
        f"[filter] 质量门控完成 — 总计:{total} 通过:{passed} "
        f"去重拒:{rej_dedup} 质量拒:{rej_qual}"
    )

    new_state["train_pool_count"] = new_state.get("train_pool_count", 0) + passed
    new_state["pending_quality_count"] = max(
        0, new_state.get("pending_quality_count", 0) - total
    )

    # DPO 触发检查（失败不影响主流程）
    try:
        import dpo_collector
        if dpo_collector.should_trigger_dpo():
            pool_count = dpo_collector.get_pool_count()
            print(f"[main] DPO 池达到 {pool_count} 条，触发 DPO 训练")
            dpo_collector.export_for_training()
            print("[main] DPO 数据集已导出，等待 train_dpo.py 实现")
    except Exception:
        pass

    return transition(new_state, "IDLE")


def run_training_phase(state: dict) -> dict:
    """执行训练阶段：检查触发条件，满足则启动完整训练周期。

    流程：
      1. check_trigger() — 未触发则转换到 IDLE
      2. run_auto_cycle() — 阻塞等待训练完成
      3. 更新 last_train_at，转换到 EVALUATING

    Args:
        state: 当前状态字典。

    Returns:
        更新后的状态字典。
    """
    new_state = dict(state)

    should_train, mode = auto_trainer.check_trigger()
    if not should_train:
        print("[training] 未达到训练触发条件，返回 IDLE")
        return transition(new_state, "IDLE")

    print(f"[training] 触发训练，模式：{mode}，启动 run_auto_cycle()")
    auto_trainer.run_auto_cycle(mode=mode)

    new_state["last_train_at"] = datetime.now().isoformat()
    new_state["train_pool_count"] = 0  # 训练后重置计数
    print("[training] 训练周期完成")

    return transition(new_state, "EVALUATING")


def run_eval_phase(state: dict) -> dict:
    """执行评估阶段：获取最新 adapter 路径并运行完整评估周期。

    流程：
      1. model_registry.get_active() — 获取当前激活 adapter
      2. eval_loop.run_full_eval_cycle(adapter_path) — 运行评估
      3. 更新 last_eval_at，转换到 IDLE

    Args:
        state: 当前状态字典。

    Returns:
        更新后的状态字典。
    """
    new_state = dict(state)

    active = model_registry.get_active()
    if active is None:
        print("[eval] 未找到激活模型，跳过评估，返回 IDLE")
        new_state["last_eval_at"] = datetime.now().isoformat()
        return transition(new_state, "IDLE")

    adapter_path = active.get("adapter_path", "")
    version = active.get("version")
    print(f"[eval] 激活模型：{active.get('version', '?')}  路径：{adapter_path}")

    if _EVAL_LOOP_AVAILABLE:
        _eval_loop_mod.run_full_eval_cycle(adapter_path, version=version)
    else:
        print("[eval] eval_loop.run_full_eval_cycle 尚未实现，跳过评估步骤")

    new_state["last_eval_at"] = datetime.now().isoformat()
    print("[eval] 评估完成")

    return transition(new_state, "IDLE")


# ─── 主循环 ───────────────────────────────────────────────────────────────────

def _write_heartbeat() -> None:
    """写入心跳文件，记录当前 ISO8601 时间戳。"""
    os.makedirs(os.path.dirname(HEARTBEAT_PATH), exist_ok=True)
    with open(HEARTBEAT_PATH, "w", encoding="utf-8") as f:
        f.write(datetime.now().isoformat())


def _is_paused(state: dict) -> bool:
    """检查系统是否处于暂停状态（error_count > 3 触发的 24h 冷却）。

    Args:
        state: 当前状态字典。

    Returns:
        True 表示仍在暂停期内。
    """
    paused_until = state.get("paused_until")
    if not paused_until:
        return False
    try:
        until_dt = datetime.fromisoformat(paused_until)
        if datetime.now() < until_dt:
            return True
    except ValueError:
        pass
    return False


def _step(state: dict) -> dict:
    """根据当前 phase 执行一步状态机转换。

    Args:
        state: 当前状态字典。

    Returns:
        执行后的新状态字典。
    """
    phase = state.get("phase", "IDLE")

    if phase == "IDLE":
        should_train, _ = auto_trainer.check_trigger()
        if should_train:
            return run_training_phase(transition(state, "TRAINING"))
        return run_distill_phase(transition(state, "DISTILLING"))

    if phase == "DISTILLING":
        return run_distill_phase(state)

    if phase == "FILTERING":
        return run_filter_phase(state)

    if phase == "TRAINING":
        return run_training_phase(state)

    if phase == "EVALUATING":
        return run_eval_phase(state)

    if phase == "DEPLOYING":
        print("[deploy] 部署阶段完成，返回 IDLE")
        return transition(state, "IDLE")

    print(f"[step] 未知阶段 {phase!r}，重置为 IDLE")
    return transition(state, "IDLE")


def main_loop(interval_seconds: int = 60) -> None:
    """主守护循环，每 interval_seconds 秒执行一次状态机步骤。

    - 写入心跳文件（D:/GIT/data/heartbeat.txt）
    - 捕获所有异常，连续错误 > 3 次则暂停 24h
    - Ctrl+C 优雅退出并保存最终状态

    Args:
        interval_seconds: 每轮轮询间隔秒数，默认 60。
    """
    print(f"[main_loop] 守护进程启动，轮询间隔 {interval_seconds}s")
    state = load_state()

    try:
        while True:
            _write_heartbeat()

            now_str = datetime.now().strftime("%H:%M:%S")
            pool = state.get("train_pool_count", 0)
            today = state.get("distill_count_today", 0)
            errors = state.get("error_count", 0)
            phase = state.get("phase", "IDLE")
            print(f"[{now_str}] phase={phase} pool={pool} today={today} errors={errors}")

            if _is_paused(state):
                until = state.get("paused_until", "?")
                print(f"[main_loop] 系统暂停中，恢复时间：{until}")
                time.sleep(interval_seconds)
                continue

            try:
                state = _step(state)
                if state.get("error_count", 0) > 0:
                    state = dict(state)
                    state["error_count"] = 0
                    state["paused_until"] = None
                save_state(state)

            except Exception as exc:  # noqa: BLE001
                state = dict(state)
                state["error_count"] = state.get("error_count", 0) + 1
                print(f"[main_loop] 异常（第 {state['error_count']} 次）：{exc}")

                if state["error_count"] > 3:
                    resume_at = (datetime.now() + timedelta(hours=24)).isoformat()
                    state["paused_until"] = resume_at
                    print(f"[main_loop] 连续错误超过 3 次，暂停 24h，恢复时间：{resume_at}")

                save_state(state)

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n[main_loop] 收到 Ctrl+C，优雅退出")
        save_state(state)
        print("[main_loop] 状态已保存，进程退出")
        sys.exit(0)


# ─── 状态摘要 ─────────────────────────────────────────────────────────────────

def print_status() -> None:
    """打印当前系统状态摘要（供 --status 参数调用）。"""
    state = load_state()

    phase = state.get("phase", "?")
    entered = state.get("phase_entered_at", "?")
    pool = state.get("train_pool_count", 0)
    today = state.get("distill_count_today", 0)
    pending = state.get("pending_quality_count", 0)
    last_train = state.get("last_train_at") or "从未"
    last_eval = state.get("last_eval_at") or "从未"
    errors = state.get("error_count", 0)
    paused = state.get("paused_until") or "否"

    print("=" * 50)
    print("  LiMa 自动蒸馏系统 — 状态摘要")
    print("=" * 50)
    print(f"  当前阶段     : {phase}")
    print(f"  阶段进入时间 : {entered}")
    print(f"  训练池样本数 : {pool}")
    print(f"  今日蒸馏数   : {today}")
    print(f"  待质检数     : {pending}")
    print(f"  上次训练     : {last_train}")
    print(f"  上次评估     : {last_eval}")
    print(f"  连续错误次数 : {errors}")
    print(f"  暂停至       : {paused}")
    print("=" * 50)


# ─── 入口 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LiMa 自动蒸馏守护进程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start", action="store_true", help="启动守护进程")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    parser.add_argument("--reset", action="store_true", help="重置状态机到 IDLE")
    parser.add_argument("--interval", type=int, default=60, help="轮询间隔秒数（默认 60）")
    args = parser.parse_args()

    if args.status:
        print_status()
    elif args.reset:
        save_state(_initial_state())
        print("[reset] 状态机已重置为 IDLE")
    elif args.start:
        main_loop(args.interval)
    else:
        parser.print_help()
