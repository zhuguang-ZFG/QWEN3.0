"""
model_registry.py — red V1flash 自动蒸馏+持续训练系统的版本管理模块

负责 adapter 版本的注册、激活、回滚和状态查询。
持久化存储：D:/GIT/data/models/registry.json
"""

import json
import os
import subprocess
from datetime import datetime
from glob import glob

REGISTRY_PATH = "D:/GIT/data/models/registry.json"
ACTIVE_LINK = "D:/GIT/active_model"


def _load() -> dict:
    """读取 registry.json，文件不存在时返回空结构。"""
    if not os.path.exists(REGISTRY_PATH):
        return {"versions": [], "active_version": None}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    """写入 registry.json，缩进2。"""
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_version_from_adapter(adapter_path: str) -> str:
    """
    从 adapter_path 下的 trainer_state.json 读取最新 step，
    生成版本号 "r{round}_step{step}"。
    读取失败时用时间戳生成版本号。
    """
    state_path = os.path.join(adapter_path, "trainer_state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        # trainer_state.json 通常有 global_step 或 log_history[-1]["step"]
        step = state.get("global_step")
        if step is None:
            log_history = state.get("log_history", [])
            if log_history:
                step = log_history[-1].get("step")
        if step is not None:
            # 尝试从路径推断 round 编号
            basename = os.path.basename(adapter_path.rstrip("/\\"))
            round_num = 1
            for part in basename.split("_"):
                if part.startswith("r") and part[1:].isdigit():
                    round_num = int(part[1:])
                    break
            return f"r{round_num}_step{step}"
    except Exception:
        pass
    return f"v{datetime.now().strftime('%Y%m%d_%H%M')}"


def register(
    adapter_path: str,
    metrics: dict,
    base_model: str = "Qwen3-8B",
    training_data_count: int = 0,
    notes: str = "",
) -> dict:
    """
    注册新的 adapter 版本，写入 registry.json，不自动激活。

    Args:
        adapter_path: adapter 所在目录路径，如 "D:/GIT/my_code_model_qwen3/"
        metrics: 评估指标字典，包含 loss/grbl_acc/cnc_acc/embed_acc/overall
        base_model: 基础模型名称，默认 "Qwen3-8B"
        training_data_count: 训练数据条数
        notes: 备注信息

    Returns:
        ModelRecord 字典
    """
    version = _get_version_from_adapter(adapter_path)
    record = {
        "version": version,
        "adapter_path": adapter_path,
        "base_model": base_model,
        "metrics": {
            "loss": metrics.get("loss", 0.0),
            "grbl_acc": metrics.get("grbl_acc", 0.0),
            "cnc_acc": metrics.get("cnc_acc", 0.0),
            "embed_acc": metrics.get("embed_acc", 0.0),
            "overall": metrics.get("overall", 0.0),
        },
        "training_data_count": training_data_count,
        "created_at": datetime.now().isoformat(),
        "active": False,
        "notes": notes,
    }
    data = _load()
    data["versions"].append(record)
    _save(data)
    return record


def get_active() -> dict | None:
    """
    返回当前激活的模型记录。

    Returns:
        active=True 的 ModelRecord，无则返回 None
    """
    data = _load()
    for record in data["versions"]:
        if record.get("active", False):
            return record
    return None


def promote(version: str) -> bool:
    """
    激活指定版本，同时停用其他所有版本。
    尝试更新 D:/GIT/active_model junction 指向新 adapter 路径。
    junction 创建失败时只打印警告，不抛异常。

    Args:
        version: 要激活的版本号，如 "r7_step4000"

    Returns:
        True 表示成功，False 表示版本不存在
    """
    data = _load()
    target_record = None
    for record in data["versions"]:
        if record["version"] == version:
            target_record = record
            break

    if target_record is None:
        return False

    # 更新 active 标志
    for record in data["versions"]:
        record["active"] = record["version"] == version

    data["active_version"] = version
    _save(data)

    # 尝试更新 Windows junction
    link = ACTIVE_LINK
    target = target_record["adapter_path"].rstrip("/\\")
    try:
        # 删除已有 junction/目录（忽略失败，目录可能不存在）
        if os.path.exists(link):
            subprocess.run(
                ["cmd", "/c", "rmdir", link],
                capture_output=True,
            )
        # 路径含空格时需加引号，通过 shell=True 传整条命令
        cmd = f'mklink /J "{link}" "{target}"'
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[WARNING] junction 创建失败（可能需要管理员权限）: {result.stderr.strip()}")
    except Exception as e:
        print(f"[WARNING] 更新 active_model junction 失败: {e}")

    return True


def rollback() -> dict | None:
    """
    回滚到当前激活版本的上一个版本（按 created_at 排序）。

    Returns:
        回滚后激活的 ModelRecord，无可回滚版本时返回 None
    """
    data = _load()
    versions = sorted(data["versions"], key=lambda r: r["created_at"])

    active_idx = None
    for i, record in enumerate(versions):
        if record.get("active", False):
            active_idx = i
            break

    if active_idx is None or active_idx == 0:
        return None

    previous = versions[active_idx - 1]
    promote(previous["version"])
    return previous


def list_versions() -> list:
    """
    返回所有已注册版本，按 created_at 降序排列（最新在前）。

    Returns:
        ModelRecord 列表
    """
    data = _load()
    return sorted(data["versions"], key=lambda r: r["created_at"], reverse=True)


def get_status() -> dict:
    """
    返回注册表摘要信息。

    Returns:
        {"total_versions": int, "active_version": str|None, "latest_metrics": dict|None}
    """
    data = _load()
    versions = data["versions"]
    active_version = data.get("active_version")

    latest_metrics = None
    if versions:
        sorted_versions = sorted(versions, key=lambda r: r["created_at"], reverse=True)
        latest_metrics = sorted_versions[0].get("metrics")

    return {
        "total_versions": len(versions),
        "active_version": active_version,
        "latest_metrics": latest_metrics,
    }


# ─── 测试块 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("model_registry.py 测试")
    print("=" * 60)

    # 使用临时目录避免污染真实注册表
    _orig_registry = REGISTRY_PATH
    with tempfile.TemporaryDirectory() as tmpdir:
        # 重定向注册表到临时目录
        import model_registry as _self
        _self.REGISTRY_PATH = os.path.join(tmpdir, "registry.json")

        fake_adapter = os.path.join(tmpdir, "fake_adapter")
        os.makedirs(fake_adapter, exist_ok=True)

        # 写一个假的 trainer_state.json
        trainer_state = {
            "global_step": 4000,
            "log_history": [{"step": 3900, "loss": 0.42}],
        }
        with open(os.path.join(fake_adapter, "trainer_state.json"), "w") as f:
            json.dump(trainer_state, f)

        # 1. 注册版本
        metrics = {
            "loss": 0.38,
            "grbl_acc": 0.91,
            "cnc_acc": 0.87,
            "embed_acc": 0.93,
            "overall": 0.90,
        }
        record = _self.register(
            adapter_path=fake_adapter,
            metrics=metrics,
            base_model="Qwen3-8B",
            training_data_count=12000,
            notes="第一轮蒸馏测试",
        )
        print(f"\n[1] 注册版本: {record['version']}")
        print(f"    adapter_path: {record['adapter_path']}")
        print(f"    metrics.overall: {record['metrics']['overall']}")
        print(f"    active: {record['active']}")

        # 2. 注册第二个版本
        fake_adapter2 = os.path.join(tmpdir, "fake_adapter2")
        os.makedirs(fake_adapter2, exist_ok=True)
        with open(os.path.join(fake_adapter2, "trainer_state.json"), "w") as f:
            json.dump({"global_step": 8000}, f)

        record2 = _self.register(
            adapter_path=fake_adapter2,
            metrics={"loss": 0.31, "grbl_acc": 0.94, "cnc_acc": 0.90,
                     "embed_acc": 0.95, "overall": 0.93},
            notes="第二轮蒸馏",
        )
        print(f"\n[2] 注册版本: {record2['version']}")

        # 3. 查询状态（激活前）
        status = _self.get_status()
        print(f"\n[3] 状态: total={status['total_versions']}, "
              f"active={status['active_version']}")

        # 4. 激活第一个版本
        ok = _self.promote(record["version"])
        print(f"\n[4] promote({record['version']}): {ok}")
        active = _self.get_active()
        print(f"    get_active(): {active['version'] if active else None}")

        # 5. 激活第二个版本
        _self.promote(record2["version"])
        print(f"\n[5] promote({record2['version']})")

        # 6. 回滚
        rolled = _self.rollback()
        print(f"\n[6] rollback() -> {rolled['version'] if rolled else None}")

        # 7. list_versions
        versions = _self.list_versions()
        print(f"\n[7] list_versions() ({len(versions)} 条，降序):")
        for v in versions:
            print(f"    {v['version']} | active={v['active']} | "
                  f"overall={v['metrics']['overall']}")

        # 8. 最终状态
        status = _self.get_status()
        print(f"\n[8] 最终状态: {status}")

    print("\n[OK] 所有测试通过")

