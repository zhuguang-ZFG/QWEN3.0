"""Core eval scoring and promotion logic (optional offline tooling)."""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import model_registry
from scripts.eval_loop_paths import (
    DOMAIN_WEIGHT,
    EVAL_SET_PATH,
    LM_STUDIO_MODEL,
    LM_STUDIO_URL,
    MAX_DOMAIN_DROP,
    RESULTS_DIR,
)

_log = logging.getLogger(__name__)


def _infer_version(adapter_path: str) -> str:
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
        _log.debug("eval_loop_core: %s", type(exc).__name__)
    return f"v{datetime.now().strftime('%Y%m%d_%H%M')}"


def _call_lm_studio(query: str, timeout: int = 30) -> str:
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
    answer_lower = answer.lower()
    for kw in keywords:
        if kw.lower() in answer_lower:
            return True
    return False


def run_eval(
    adapter_path: str,
    eval_set_path: str = EVAL_SET_PATH,
    version: str | None = None,
) -> dict:
    if version is None:
        version = _infer_version(adapter_path)
    timestamp = datetime.now().isoformat()

    with open(eval_set_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    domain_items: dict = {}
    for item in eval_set:
        intent = item.get("intent", "unknown")
        domain_items.setdefault(intent, []).append(item)

    domain_scores: dict = {}
    total_correct = 0
    total_questions = len(eval_set)
    lm_unavailable_reason = None

    lm_available = True
    try:
        _call_lm_studio("test", timeout=5)
    except urllib.error.HTTPError:
        pass
    except urllib.error.URLError as probe_err:
        lm_available = False
        lm_unavailable_reason = f"LM Studio 不可用：{probe_err}"
        print(f"[eval_loop] {lm_unavailable_reason}")
    except Exception:
        lm_available = False
        lm_unavailable_reason = "LM Studio 连接超时或未知错误"
        print(f"[eval_loop] {lm_unavailable_reason}")

    if not lm_available:
        for domain in domain_items:
            domain_scores[domain] = 0.0
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

    for d in ("grbl_config", "cnc_trouble", "embedded_dev"):
        domain_scores.setdefault(d, 0.0)

    overall = (
        domain_scores["grbl_config"] + domain_scores["cnc_trouble"] + domain_scores["embedded_dev"]
    ) * DOMAIN_WEIGHT

    return {
        "version": version,
        "adapter_path": adapter_path,
        "timestamp": timestamp,
        "domain_scores": domain_scores,
        "overall": round(overall, 4),
        "passed": True,
        "rollback_reason": None,
        "total_questions": total_questions,
        "correct_count": total_correct,
    }


def compare(new_result: dict) -> tuple:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    history_files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json")))

    if not history_files:
        return (True, "首次评估，自动通过")

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

    if new_overall < old_overall:
        reason = f"整体分数下降：{old_overall:.4f} → {new_overall:.4f}（下降 {old_overall - new_overall:.4f}）"
        return (False, reason)

    for domain in ("grbl_config", "cnc_trouble", "embedded_dev"):
        old_score = old_domains.get(domain, 0.0)
        new_score = new_domains.get(domain, 0.0)
        drop = old_score - new_score
        if drop > MAX_DOMAIN_DROP:
            reason = (
                f"域 [{domain}] 下降过大：{old_score:.4f} → {new_score:.4f}（下降 {drop:.4f} > 阈值 {MAX_DOMAIN_DROP}）"
            )
            return (False, reason)

    return (True, "")


def append_history(result: dict) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    version = result.get("version", "unknown")
    ts = result.get("timestamp", datetime.now().isoformat())
    ts_safe = ts.replace(":", "-").replace(".", "-")
    filename = f"{version}_{ts_safe}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[eval_loop] 评估结果已写入：{filepath}")


def promote_if_better(new_result: dict) -> bool:
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
