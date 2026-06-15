#!/usr/bin/env python3
"""Optional local-model eval loop (LM Studio + model_registry).

Not on the LiMa device/chat hot path. Run manually after adapter training:
  python scripts/eval_loop.py [adapter_path]

Moved from root eval_loop.py (CQ-Q5-4).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.eval_loop_core import promote_if_better, run_eval
from scripts.eval_loop_paths import DEFAULT_EVAL_SET_PATH, EVAL_SET_PATH

__all__ = [
    "create_default_eval_set",
    "run_eval",
    "compare",
    "append_history",
    "promote_if_better",
    "run_full_eval_cycle",
]


def create_default_eval_set(path: str = EVAL_SET_PATH) -> None:
    """Seed eval_set.json from bundled default_eval_set.json when missing."""
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(DEFAULT_EVAL_SET_PATH, encoding="utf-8") as src:
        data = json.load(src)
    with open(path, "w", encoding="utf-8") as dst:
        json.dump(data, dst, indent=2, ensure_ascii=False)
    print(f"[eval_loop] 创建默认评估集：{path}，共 {len(data)} 条")


def run_full_eval_cycle(adapter_path: str, version: str | None = None) -> dict:
    print("\n[eval_loop] ===== 开始评估周期 =====")
    print(f"[eval_loop] adapter_path: {adapter_path}")

    create_default_eval_set()
    print("[eval_loop] 正在推理评估...")
    result = run_eval(adapter_path, version=version)
    promoted = promote_if_better(result)

    print("\n[eval_loop] ===== 评估摘要 =====")
    print(f"  版本：{result['version']}")
    print(f"  总题数：{result['total_questions']}，答对：{result['correct_count']}")
    print(f"  grbl_config：{result['domain_scores'].get('grbl_config', 0):.2%}")
    print(f"  cnc_trouble：{result['domain_scores'].get('cnc_trouble', 0):.2%}")
    print(f"  embedded_dev：{result['domain_scores'].get('embedded_dev', 0):.2%}")
    print(f"  整体得分：{result['overall']:.2%}")
    print(f"  升级结果：{'已升级' if promoted else '未升级'}")
    if result.get("rollback_reason"):
        print(f"  回滚原因：{result['rollback_reason']}")
    print("[eval_loop] ===== 评估周期结束 =====\n")
    return result


# Re-export core helpers for programmatic use.
from scripts.eval_loop_core import append_history, compare  # noqa: E402


def _self_test() -> None:
    print("=" * 60)
    print("scripts/eval_loop.py 自测")
    print("=" * 60)

    create_default_eval_set()
    with open(EVAL_SET_PATH, encoding="utf-8") as fh:
        eval_set = json.load(fh)
    print(f"\n[测试1] 评估集条数：{len(eval_set)}")
    domains: dict[str, int] = {}
    for item in eval_set:
        domains[item["intent"]] = domains.get(item["intent"], 0) + 1
    for domain, count in sorted(domains.items()):
        print(f"  {domain}: {count} 条")

    print("\n[测试2] 测试 LM Studio 不可用时的降级行为...")
    fake_adapter = str(_ROOT / "fake_adapter_r1_step100")
    result = run_eval(fake_adapter)
    print(f"  overall: {result['overall']}")
    print(f"  passed: {result['passed']}")
    print(f"  rollback_reason: {result['rollback_reason']}")
    print(f"  total_questions: {result['total_questions']}")
    print("\n[测试] 全部通过")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_full_eval_cycle(sys.argv[1])
    else:
        _self_test()
