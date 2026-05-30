"""train_lock.py — 全局训练锁，防止并发训练冲突。"""
import json
import os
import time
from datetime import datetime

LOCK_FILE = "D:/GIT/data/train.lock"


def acquire(mode: str = "manual") -> bool:
    """尝试获取训练锁。返回 True 表示成功，False 表示已被占用。"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
            pid = info.get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                    # 进程仍活跃，锁被占用
                    print(
                        f"[train_lock] 训练锁已被占用：PID={pid}，"
                        f"模式={info.get('mode')}，"
                        f"启动于 {info.get('started_at')}"
                    )
                    return False
                except (OSError, ProcessLookupError):
                    # 进程已死，删除残留锁
                    print(f"[train_lock] 发现残留锁（PID={pid} 已不存在），清除")
                    os.remove(LOCK_FILE)
        except Exception as e:
            print(f"[train_lock] 读取锁文件失败，强制清除：{e}")
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass

    # 写入新锁文件
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    lock_info = {
        "pid": os.getpid(),
        "started_at": datetime.now().isoformat(),
        "mode": mode,
    }
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(lock_info, f, ensure_ascii=False, indent=2)
    print(f"[train_lock] 已获取训练锁：PID={os.getpid()}，模式={mode}")
    return True


def release() -> None:
    """释放训练锁（只能释放自己持有的锁）。"""
    if not os.path.exists(LOCK_FILE):
        return
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            info = json.load(f)
        if info.get("pid") == os.getpid():
            os.remove(LOCK_FILE)
            print(f"[train_lock] 已释放训练锁（PID={os.getpid()}）")
        else:
            print(
                f"[train_lock] 警告：当前进程 PID={os.getpid()} "
                f"不是锁持有者（PID={info.get('pid')}），不释放"
            )
    except Exception as e:
        print(f"[train_lock] 释放锁失败：{e}")


def is_locked() -> bool:
    """检查是否有训练正在运行。"""
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            info = json.load(f)
        pid = info.get("pid")
        if pid:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False
    except Exception:
        pass  # train_lock.py
    return False


def get_lock_info() -> dict | None:
    """返回当前锁的信息，无锁返回 None。"""
    if not is_locked():
        return None
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def wait_for_lock(timeout_seconds: int = 3600) -> bool:
    """等待锁释放，超时返回 False。每30秒检查一次。"""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_locked():
            return True
        remaining = int(deadline - time.time())
        print(f"[train_lock] 等待训练锁释放，剩余超时 {remaining}s ...")
        time.sleep(30)
    print(f"[train_lock] 等待超时（{timeout_seconds}s），锁仍被占用")
    return False
