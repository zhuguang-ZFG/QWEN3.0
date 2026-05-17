"""
auto_trainer.py — red V1flash 自动蒸馏+持续训练系统的训练触发模块

负责检测训练触发条件、准备数据集、启动训练进程、等待完成并注册新版本。
"""

import json
import os
import subprocess
import time
import glob
import random
from datetime import datetime, timezone

import model_registry

# ========== 路径常量 ==========
POOL_DIR = "D:/GIT/data/training_data/incremental/"
TRAIN_DATA_DIR = "D:/GIT/data/training_data/"
REGISTRY_PATH = "D:/GIT/data/models/registry.json"
STATUS_PATH = "D:/GIT/data/train_status.json"
LOG_DIR = "D:/GIT/data/logs/"
CHECKPOINT_BASE = "D:/GIT/data/models/checkpoints/"
MERGED_TEMP_PATH = "D:/GIT/data/training_data/merged_temp.json"
TRAIN_SCRIPT = "D:/GIT/train_model.py"
PYTHON_BIN = "D:/GIT/venv/Scripts/python.exe"


# ========== 辅助函数 ==========

def _count_samples(dir_path: str) -> int:
    """统计目录下所有 .json 文件的记录总数（不递归子目录）。

    Args:
        dir_path: 目标目录路径

    Returns:
        所有 .json 文件中的记录总数（列表长度之和）
    """
    total = 0
    pattern = os.path.join(dir_path, "*.json")
    for fpath in glob.glob(pattern):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                total += len(data)
        except Exception as e:
            print(f"[auto_trainer] 警告：读取 {fpath} 失败：{e}")
    return total


def _get_new_data_paths(pool_dir: str) -> list:
    """返回 pool_dir 下所有 .json 文件路径（不递归子目录）。

    Args:
        pool_dir: 增量数据池目录

    Returns:
        .json 文件路径列表
    """
    pattern = os.path.join(pool_dir, "*.json")
    return glob.glob(pattern)


# ========== 核心函数 ==========

def check_trigger(
    pool_dir: str = POOL_DIR,
    min_new_samples: int = 500,
    max_days_since_last: int = 7,
) -> tuple:
    """检查是否满足训练触发条件。

    触发条件（满足任一即触发）：
    - 新数据 >= min_new_samples 条
    - 距上次训练 >= max_days_since_last 天

    训练模式判断：
    - 新数据 >= 总训练数据量的 5% → "full"
    - 否则 → "incremental"

    Args:
        pool_dir: 增量数据池目录
        min_new_samples: 触发训练的最小新样本数
        max_days_since_last: 触发训练的最大间隔天数

    Returns:
        (should_train: bool, mode: str)，mode 为 "incremental" 或 "full"
    """
    new_count = _count_samples(pool_dir)
    print(f"[check_trigger] 新数据量：{new_count} 条")

    # 读取上次训练时间
    days_since_last = None
    last_train_time = None
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                registry = json.load(f)
            versions = registry.get("versions", [])
            if versions:
                # 取最新版本的 created_at
                latest = versions[-1]
                created_at_str = latest.get("created_at", "")
                if created_at_str:
                    last_train_time = datetime.fromisoformat(created_at_str)
                    now = datetime.now()
                    delta = now - last_train_time.replace(tzinfo=None)
                    days_since_last = delta.total_seconds() / 86400
        except Exception as e:
            print(f"[check_trigger] 读取 registry.json 失败：{e}")

    if days_since_last is not None:
        print(f"[check_trigger] 距上次训练：{days_since_last:.1f} 天")
    else:
        print("[check_trigger] 未找到历史训练记录")

    # 判断是否触发
    trigger_by_count = new_count >= min_new_samples
    trigger_by_time = (days_since_last is None) or (days_since_last >= max_days_since_last)
    should_train = trigger_by_count or trigger_by_time

    if not should_train:
        print(f"[check_trigger] 未触发：新数据 {new_count} < {min_new_samples}，"
              f"间隔 {days_since_last:.1f} 天 < {max_days_since_last} 天")
        return (False, "incremental")

    # 判断训练模式
    old_count = _count_samples(TRAIN_DATA_DIR)
    print(f"[check_trigger] 旧数据总量（不含 incremental）：{old_count} 条")
    if old_count > 0 and new_count >= old_count * 0.05:
        mode = "full"
    else:
        mode = "incremental"

    print(f"[check_trigger] 触发训练，模式：{mode}")
    return (True, mode)


def prepare_dataset(
    new_data_paths: list,
    old_data_sample_ratio: float = 0.05,
    output_path: str = MERGED_TEMP_PATH,
) -> str:
    """合并新旧数据，写入临时 JSON 文件，返回文件路径。

    新数据从 new_data_paths 读取（QAPair 格式），转换为训练格式。
    混入 old_data_sample_ratio 比例的旧数据防止灾难性遗忘。

    Args:
        new_data_paths: 新数据 .json 文件路径列表
        old_data_sample_ratio: 旧数据采样比例，默认 0.05
        output_path: 合并后输出文件路径

    Returns:
        output_path
    """
    merged = []

    # 读取新数据并转换格式
    for fpath in new_data_paths:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                records = json.load(f)
            if not isinstance(records, list):
                records = [records]
            for rec in records:
                query = rec.get("query", rec.get("question", ""))
                answer = rec.get("answer", rec.get("response", ""))
                if query and answer:
                    merged.append({
                        "messages": [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": answer},
                        ]
                    })
        except Exception as e:
            print(f"[prepare_dataset] 读取新数据 {fpath} 失败：{e}")

    print(f"[prepare_dataset] 新数据：{len(merged)} 条")

    # 采样旧数据
    old_files = glob.glob(os.path.join(TRAIN_DATA_DIR, "*.json"))
    old_records = []
    for fpath in old_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                old_records.extend(data)
        except Exception as e:
            print(f"[prepare_dataset] 读取旧数据 {fpath} 失败：{e}")

    if old_records:
        sample_size = max(1, int(len(old_records) * old_data_sample_ratio))
        sampled = random.sample(old_records, min(sample_size, len(old_records)))
        # 旧数据可能已是训练格式，也可能是 QAPair 格式
        for rec in sampled:
            if "messages" in rec:
                merged.append(rec)
            else:
                query = rec.get("query", rec.get("question", ""))
                answer = rec.get("answer", rec.get("response", ""))
                if query and answer:
                    merged.append({
                        "messages": [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": answer},
                        ]
                    })
        print(f"[prepare_dataset] 混入旧数据：{len(sampled)} 条，合计：{len(merged)} 条")

    random.shuffle(merged)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"[prepare_dataset] 数据集已写入：{output_path}")
    return output_path


def start_training(
    mode: str = "incremental",
    dataset_path: str = None,
    resume_checkpoint: str = None,
) -> subprocess.Popen:
    """启动训练子进程（调用 train_model.py），返回进程对象。

    读取当前激活的 adapter 路径，构建训练命令并以 subprocess.Popen 启动。
    stdout/stderr 重定向到日志文件，写入状态文件 train_status.json。

    Args:
        mode: 训练模式，"incremental"（2000步）或 "full"（4000步）
        dataset_path: 训练数据集路径，None 时使用默认路径
        resume_checkpoint: 断点续训路径，None 时不传该参数

    Returns:
        subprocess.Popen 对象
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(CHECKPOINT_BASE, f"run_{timestamp}") + "/"
    max_steps = 2000 if mode == "incremental" else 4000

    if dataset_path is None:
        dataset_path = MERGED_TEMP_PATH

    # 构建命令
    cmd = [
        PYTHON_BIN,
        TRAIN_SCRIPT,
        "--dataset", dataset_path,
        "--output_dir", output_dir,
        "--max_steps", str(max_steps),
    ]
    if resume_checkpoint:
        cmd += ["--resume_from_checkpoint", resume_checkpoint]

    # 准备日志文件
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"train_{timestamp}.log")

    print(f"[start_training] 启动训练，模式={mode}，步数={max_steps}")
    print(f"[start_training] 日志：{log_path}")
    print(f"[start_training] 输出目录：{output_dir}")

    log_file = open(log_path, "w", encoding="utf-8")
    popen = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        cwd="D:/GIT",
    )

    # 写入状态文件
    status = {
        "running": True,
        "pid": popen.pid,
        "started_at": datetime.now().isoformat(),
        "mode": mode,
        "output_dir": output_dir,
        "log_path": log_path,
        "max_steps": max_steps,
    }
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)

    print(f"[start_training] 进程已启动，PID={popen.pid}")
    return popen


def get_status() -> dict:
    """返回当前训练状态。

    读取 train_status.json，检查进程是否存活，
    读取最新 checkpoint 的 trainer_state.json 获取 step/loss。

    Returns:
        {
            "running": bool,
            "step": int,
            "max_steps": int,
            "loss": float,
            "eta_minutes": int,
            "output_dir": str,
        }
        文件不存在时返回 {"running": False}
    """
    if not os.path.exists(STATUS_PATH):
        return {"running": False}

    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            status = json.load(f)
    except Exception as e:
        print(f"[get_status] 读取状态文件失败：{e}")
        return {"running": False}

    running = status.get("running", False)
    pid = status.get("pid")
    output_dir = status.get("output_dir", "")
    max_steps = status.get("max_steps", 2000)

    # 检查进程是否存活
    if running and pid:
        try:
            os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            running = False

    # 读取最新 checkpoint 的 trainer_state.json
    step = 0
    loss = 0.0
    eta_minutes = 0

    if output_dir and os.path.isdir(output_dir):
        # 查找最新 checkpoint 子目录
        checkpoint_dirs = sorted(
            glob.glob(os.path.join(output_dir, "checkpoint-*")),
            key=lambda p: int(p.rsplit("-", 1)[-1]) if p.rsplit("-", 1)[-1].isdigit() else 0,
        )
        state_path = None
        if checkpoint_dirs:
            state_path = os.path.join(checkpoint_dirs[-1], "trainer_state.json")
        # 也检查 output_dir 根目录
        root_state = os.path.join(output_dir, "trainer_state.json")
        if not state_path or not os.path.exists(state_path):
            if os.path.exists(root_state):
                state_path = root_state

        if state_path and os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    trainer_state = json.load(f)
                step = trainer_state.get("global_step", 0)
                log_history = trainer_state.get("log_history", [])
                if log_history:
                    for entry in reversed(log_history):
                        if "loss" in entry:
                            loss = entry["loss"]
                            break
                # 估算剩余时间
                if step > 0 and running:
                    started_at_str = status.get("started_at", "")
                    if started_at_str:
                        started_at = datetime.fromisoformat(started_at_str)
                        elapsed = (datetime.now() - started_at).total_seconds()
                        steps_per_sec = step / elapsed if elapsed > 0 else 0
                        remaining_steps = max_steps - step
                        if steps_per_sec > 0:
                            eta_minutes = int(remaining_steps / steps_per_sec / 60)
            except Exception as e:
                print(f"[get_status] 读取 trainer_state.json 失败：{e}")

    return {
        "running": running,
        "step": step,
        "max_steps": max_steps,
        "loss": loss,
        "eta_minutes": eta_minutes,
        "output_dir": output_dir,
    }


def wait_and_register(
    popen: subprocess.Popen,
    output_dir: str,
    training_data_count: int,
) -> dict | None:
    """等待训练进程完成，成功后注册新版本。

    Args:
        popen: start_training 返回的 Popen 对象
        output_dir: 训练输出目录（adapter 路径）
        training_data_count: 本次训练使用的数据条数

    Returns:
        成功时返回 ModelRecord 字典，失败时返回 None
    """
    print(f"[wait_and_register] 等待训练进程完成（PID={popen.pid}）...")
    popen.wait()
    returncode = popen.returncode
    print(f"[wait_and_register] 进程退出，returncode={returncode}")

    if returncode == 0:
        # 读取最终 loss
        final_loss = 0.0
        state_path = os.path.join(output_dir, "trainer_state.json")
        # 也检查最新 checkpoint
        checkpoint_dirs = sorted(
            glob.glob(os.path.join(output_dir, "checkpoint-*")),
            key=lambda p: int(p.rsplit("-", 1)[-1]) if p.rsplit("-", 1)[-1].isdigit() else 0,
        )
        if checkpoint_dirs:
            cp_state = os.path.join(checkpoint_dirs[-1], "trainer_state.json")
            if os.path.exists(cp_state):
                state_path = cp_state

        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    trainer_state = json.load(f)
                log_history = trainer_state.get("log_history", [])
                for entry in reversed(log_history):
                    if "loss" in entry:
                        final_loss = entry["loss"]
                        break
            except Exception as e:
                print(f"[wait_and_register] 读取 trainer_state.json 失败：{e}")

        # 注册新版本
        record = model_registry.register(
            adapter_path=output_dir,
            metrics={"loss": final_loss},
            training_data_count=training_data_count,
        )
        print(f"[wait_and_register] 已注册新版本：{record.get('version')}，loss={final_loss:.4f}")

        # 更新状态文件
        _update_status({"running": False, "completed_at": datetime.now().isoformat()})
        return record
    else:
        print(f"[wait_and_register] 训练失败，returncode={returncode}")
        _update_status({"running": False, "failed_at": datetime.now().isoformat(), "returncode": returncode})
        return None


def _update_status(updates: dict) -> None:
    """更新 train_status.json 中的字段。

    Args:
        updates: 要更新的键值对
    """
    status = {}
    if os.path.exists(STATUS_PATH):
        try:
            with open(STATUS_PATH, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            pass
    status.update(updates)
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def run_auto_cycle() -> None:
    """完整的一次自动训练周期。

    执行流程：check_trigger → prepare_dataset → start_training → wait_and_register
    训练完成后提示运行 eval_loop.py 评估新模型。
    """
    print("[run_auto_cycle] 开始自动训练周期...")

    # 1. 检查触发条件
    should_train, mode = check_trigger()
    if not should_train:
        print("[run_auto_cycle] 未满足触发条件，跳过本次训练。")
        return

    # 2. 准备数据集
    new_data_paths = _get_new_data_paths(POOL_DIR)
    if not new_data_paths:
        print("[run_auto_cycle] 增量数据池为空，跳过训练。")
        return

    dataset_path = prepare_dataset(new_data_paths)

    # 统计本次训练数据总量
    training_data_count = _count_samples(os.path.dirname(dataset_path))

    # 3. 启动训练
    popen = start_training(mode=mode, dataset_path=dataset_path)
    with open(STATUS_PATH, "r", encoding="utf-8") as f:
        output_dir = json.load(f).get("output_dir", "")

    # 4. 等待完成并注册
    record = wait_and_register(popen, output_dir, training_data_count)

    if record:
        print(f"\n训练完成，请运行 eval_loop.py 评估新模型")
        print(f"  新版本：{record.get('version')}")
        print(f"  adapter 路径：{record.get('adapter_path')}")
    else:
        print("[run_auto_cycle] 训练失败，请检查日志。")


# ========== 测试块 ==========

if __name__ == "__main__":
    print("=" * 60)
    print("auto_trainer.py 测试")
    print("=" * 60)

    print("\n--- check_trigger() ---")
    should_train, mode = check_trigger()
    print(f"结果：should_train={should_train}, mode={mode}")

    print("\n--- get_status() ---")
    status = get_status()
    print(f"结果：{json.dumps(status, ensure_ascii=False, indent=2)}")
