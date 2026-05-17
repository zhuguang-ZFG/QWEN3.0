"""dpo_collector.py — DPO 负样本收集器。
从 quality_gate 的评分结果中自动构建 DPO 训练三元组。
Superpower 原则：拒绝的数据不是废料，是最宝贵的对齐信号。
"""

import json
import os
import glob
import time
from datetime import datetime

import quality_gate

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DPO_POOL_DIR = "D:/GIT/data/dpo_pool/"
DPO_TRIGGER_COUNT = 200  # 积累200条三元组触发DPO训练

_CHOSEN_THRESHOLD = 0.75   # chosen 最低分
_REJECTED_CEILING = 0.5    # rejected 最高分
_MIN_SCORE_GAP    = 0.3    # 最小分差


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _score_single_answer(qa_pair: dict, answer: str) -> float:
    """对单条回答单独评分，复用 quality_gate.score 逻辑。"""
    single = dict(qa_pair)
    single['answer'] = answer
    single['all_answers'] = [answer]
    detail = quality_gate.score(single)
    return detail['total']


def _write_triple(triple: dict) -> None:
    """将单条 DPO 三元组写入 DPO_POOL_DIR，文件名含时间戳+随机后缀。"""
    os.makedirs(DPO_POOL_DIR, exist_ok=True)
    ts = int(time.time() * 1000)
    fname = f"triple_{ts}.json"
    fpath = os.path.join(DPO_POOL_DIR, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(triple, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def collect_from_batch(qa_pairs: list, score_details: list) -> int:
    """从一批评分结果中提取 DPO 三元组。

    qa_pairs:     QAPair 字典列表（含 all_answers 字段）
    score_details: 对应的 ScoreDetail 列表（可为空列表，此时忽略）

    逻辑：
    - 对每个 QAPair，若 all_answers 有 >= 2 个回答
    - 对每个回答单独评分
    - 找出最高分（chosen）和最低分（rejected）
    - 若 score_gap >= 0.3 且 chosen >= 0.75 且 rejected < 0.5
    - 构建 DPOTriple 写入 DPO_POOL_DIR

    Returns:
        写入的三元组数量。
    """
    written = 0

    for pair in qa_pairs:
        all_answers = pair.get('all_answers', [])
        if not all_answers or len(all_answers) < 2:
            continue

        # 对每个回答单独评分
        scored = []
        for ans in all_answers:
            if not ans or not ans.strip():
                continue
            s = _score_single_answer(pair, ans)
            scored.append((s, ans))

        if len(scored) < 2:
            continue

        scored.sort(key=lambda x: x[0])
        rejected_score, rejected_ans = scored[0]
        chosen_score,   chosen_ans   = scored[-1]

        score_gap = chosen_score - rejected_score

        if (chosen_score >= _CHOSEN_THRESHOLD
                and rejected_score < _REJECTED_CEILING
                and score_gap >= _MIN_SCORE_GAP):

            triple = {
                "query":          pair.get('query', ''),
                "chosen":         chosen_ans,
                "rejected":       rejected_ans,
                "chosen_score":   round(chosen_score,   4),
                "rejected_score": round(rejected_score, 4),
                "score_gap":      round(score_gap,      4),
                "intent":         pair.get('intent', ''),
                "created_at":     datetime.now().isoformat(),
            }
            _write_triple(triple)
            written += 1

    return written


def get_pool_count() -> int:
    """返回当前 DPO 池中的三元组数量。"""
    if not os.path.isdir(DPO_POOL_DIR):
        return 0
    pattern = os.path.join(DPO_POOL_DIR, "triple_*.json")
    return len(glob.glob(pattern))


def should_trigger_dpo() -> bool:
    """是否达到 DPO 训练触发条件。"""
    return get_pool_count() >= DPO_TRIGGER_COUNT


def load_pool(max_count: int = None) -> list:
    """加载 DPO 池中的三元组，用于训练。

    Args:
        max_count: 最多加载条数，None 表示全部。

    Returns:
        DPOTriple 字典列表，按 created_at 升序排列。
    """
    if not os.path.isdir(DPO_POOL_DIR):
        return []

    pattern = os.path.join(DPO_POOL_DIR, "triple_*.json")
    files = sorted(glob.glob(pattern))

    if max_count is not None:
        files = files[:max_count]

    triples = []
    for fpath in files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                triples.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue

    return triples


def export_for_training(
    output_path: str = "D:/GIT/data/training_data/dpo_dataset.json"
) -> str:
    """将 DPO 池导出为训练格式，返回文件路径。

    训练格式（兼容 trl DPOTrainer）：
    [{"prompt": query, "chosen": chosen, "rejected": rejected}, ...]
    """
    triples = load_pool()
    if not triples:
        return output_path

    dataset = [
        {
            "prompt":   t["query"],
            "chosen":   t["chosen"],
            "rejected": t["rejected"],
        }
        for t in triples
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"[dpo_collector] 导出 {len(dataset)} 条三元组 → {output_path}")
    return output_path


def clear_pool() -> None:
    """训练完成后清空 DPO 池（保留最近100条作为种子）。"""
    if not os.path.isdir(DPO_POOL_DIR):
        return

    pattern = os.path.join(DPO_POOL_DIR, "triple_*.json")
    files = sorted(glob.glob(pattern))

    # 保留最新 100 条
    to_delete = files[:-100] if len(files) > 100 else []
    for fpath in to_delete:
        try:
            os.remove(fpath)
        except OSError:
            pass

    print(f"[dpo_collector] 清空 DPO 池：删除 {len(to_delete)} 条，保留 {min(len(files), 100)} 条种子")
