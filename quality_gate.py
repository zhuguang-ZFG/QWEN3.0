"""
quality_gate.py — 质量门控模块

red V1flash 自动蒸馏+持续训练系统的第一个模块。
负责对蒸馏生成的 Q&A 对进行多维度质量评分，过滤低质量样本，
确保只有高质量的 Q&A 对进入训练集。

评分维度：
  - accuracy (0.4)：GRBL 参数范围验证
  - completeness (0.25)：回答长度/结构
  - consistency (0.2)：多模型回答词袋一致性
  - format (0.15)：代码块/单位/步骤格式

依赖：json, os, re, math, hashlib, glob（全部标准库）
"""

import json
import os
import re
import math
import hashlib
import glob


# ---------------------------------------------------------------------------
# GRBL 参数合法范围表
# ---------------------------------------------------------------------------
GRBL_PARAM_RANGES = {
    0:   (1,      255),
    1:   (0,      255),
    2:   (0,      7),
    3:   (0,      7),
    4:   (0,      1),
    5:   (0,      1),
    6:   (0,      1),
    10:  (0,      255),
    11:  (0.0,    10.0),
    12:  (0.0,    1.0),
    13:  (0,      1),
    20:  (0,      1),
    21:  (0,      1),
    22:  (0,      1),
    23:  (0,      7),
    24:  (1,      10000),
    25:  (1,      100000),
    26:  (0,      255),
    27:  (0,      100),
    30:  (1,      100000),
    31:  (0,      100000),
    32:  (0,      1),
    100: (1,      10000),
    101: (1,      10000),
    102: (1,      10000),
    110: (1,      100000),
    111: (1,      100000),
    112: (1,      100000),
    120: (1,      100000),
    121: (1,      100000),
    122: (1,      100000),
    130: (0,      100000),
    131: (0,      100000),
    132: (0,      100000),
}

# GRBL 参数提取正则
_GRBL_RE = re.compile(r'\$(\d+)\s*[=:]\s*([\d.]+)')

# PII 替换正则
_IP_RE      = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_PHONE_RE   = re.compile(r'\b1[3-9]\d{9}\b')
_EMAIL_RE   = re.compile(r'\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b')
_WIN_PATH_RE = re.compile(r'\b[A-Za-z]:[/\\][\w/\\. -]*')
_UNIX_PATH_RE = re.compile(r'(?<!\w)(?:/home|/usr|/etc|/var|/tmp|/opt|/root)/[\w/. -]*')
_COMPANY_RE = re.compile(
    r'(?:深圳|广州|北京|上海)[\w]*?(?:科技|电子|机械|有限公司)'
)


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _score_accuracy(answer: str) -> float:
    """提取回答中的 GRBL 参数值，与合法范围对比，返回 0.0-1.0。"""
    matches = _GRBL_RE.findall(answer)
    if not matches:
        return 1.0  # 无参数不扣分

    total = len(matches)
    valid = 0
    for param_str, value_str in matches:
        param_id = int(param_str)
        try:
            value = float(value_str)
        except ValueError:
            continue
        if param_id in GRBL_PARAM_RANGES:
            lo, hi = GRBL_PARAM_RANGES[param_id]
            if lo <= value <= hi:
                valid += 1
        else:
            # 未知参数不扣分（不在规范表中）
            valid += 1

    return valid / total if total > 0 else 1.0


def _score_completeness(answer: str) -> float:
    """根据回答长度计算完整性分数。"""
    length = len(answer)
    if length >= 100 and length <= 2000:
        return 1.0
    elif length < 50:
        return 0.0
    elif length < 100:
        # 50-100 线性插值 0.0 -> 1.0
        return (length - 50) / 50.0
    else:
        # >2000 线性衰减到 0.7（2000->1.0, 5000->0.7，超过5000保持0.7）
        decay_start = 2000
        decay_end   = 5000
        if length >= decay_end:
            return 0.7
        ratio = (length - decay_start) / (decay_end - decay_start)
        return 1.0 - ratio * 0.3


def _jaccard(set_a: set, set_b: set) -> float:
    """计算两个集合的 Jaccard 相似度。"""
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _score_consistency(all_answers: list) -> float:
    """用词袋 Jaccard 相似度计算多模型回答一致性。"""
    if not all_answers or len(all_answers) == 1:
        return 0.8  # 中性分

    # 将每个回答转为词集合（按空白/标点分词）
    word_sets = []
    for ans in all_answers:
        words = set(re.findall(r'\w+', ans.lower()))
        word_sets.append(words)

    # 两两 Jaccard，取均值
    scores = []
    n = len(word_sets)
    for i in range(n):
        for j in range(i + 1, n):
            scores.append(_jaccard(word_sets[i], word_sets[j]))

    return sum(scores) / len(scores) if scores else 0.8


def _score_format(answer: str) -> float:
    """检查格式规范：代码块闭合、数字/单位、步骤编号/列表。"""
    score = 0.0

    # 代码块闭合检查（``` 出现次数为偶数）
    backtick_count = answer.count('```')
    if backtick_count > 0 and backtick_count % 2 == 0:
        score += 0.4

    # 包含数字+单位（mm/rpm/mm/min/Hz/V/A/°/度/步/脉冲等）
    unit_pattern = re.compile(
        r'\d+\s*(?:mm|rpm|mm/min|Hz|kHz|MHz|V|A|W|°|度|步|脉冲|pulse|step|m/s|cm|μm|us|ms|s)\b',
        re.IGNORECASE
    )
    if unit_pattern.search(answer):
        score += 0.3

    # 包含步骤编号（1. 2. 3. 或 1、2、3 或 - 列表）
    step_pattern = re.compile(
        r'(?:^|\n)\s*(?:\d+[.、。]\s+|\-\s+|\*\s+)',
        re.MULTILINE
    )
    if step_pattern.search(answer):
        score += 0.3

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def score(qa_pair: dict, threshold: float = 0.75) -> dict:
    """对单条 Q&A 对进行质量评分。

    Args:
        qa_pair: 包含 query/answer/intent/source_backend/
                 teacher_backends/all_answers 的字典。
        threshold: 通过阈值，默认 0.75。

    Returns:
        ScoreDetail 字典，包含 total/accuracy/completeness/
        consistency/format/passed/rejection_reason。
    """
    answer      = qa_pair.get('answer', '')
    all_answers = qa_pair.get('all_answers', [answer]) or [answer]

    acc   = _score_accuracy(answer)
    comp  = _score_completeness(answer)
    cons  = _score_consistency(all_answers)
    fmt   = _score_format(answer)

    total = acc * 0.4 + comp * 0.25 + cons * 0.2 + fmt * 0.15
    passed = total >= threshold

    # 构建拒绝原因
    rejection_reason = ''
    if not passed:
        reasons = []
        if acc < 0.6:
            reasons.append(f'accuracy={acc:.2f}(GRBL参数超范围)')
        if comp < 0.5:
            reasons.append(f'completeness={comp:.2f}(回答过短或过长)')
        if cons < 0.5:
            reasons.append(f'consistency={cons:.2f}(多模型回答差异大)')
        if fmt < 0.3:
            reasons.append(f'format={fmt:.2f}(格式不规范)')
        if not reasons:
            reasons.append(f'total={total:.2f}<threshold={threshold}')
        rejection_reason = '; '.join(reasons)

    return {
        'total':            round(total, 4),
        'accuracy':         round(acc,   4),
        'completeness':     round(comp,  4),
        'consistency':      round(cons,  4),
        'format':           round(fmt,   4),
        'passed':           passed,
        'rejection_reason': rejection_reason,
    }


def filter_batch(pairs: list, threshold: float = 0.75) -> tuple:
    """批量过滤 Q&A 对。

    Args:
        pairs: QAPair 字典列表。
        threshold: 通过阈值，默认 0.75。

    Returns:
        (passed_list, rejected_list) 元组，每条记录附加 score_detail 字段。
    """
    passed_list   = []
    rejected_list = []

    for pair in pairs:
        detail = score(pair, threshold=threshold)
        enriched = dict(pair)
        enriched['score_detail'] = detail
        if detail['passed']:
            passed_list.append(enriched)
        else:
            rejected_list.append(enriched)

    return passed_list, rejected_list


# ---------------------------------------------------------------------------
# MinHash 去重（手动实现，不依赖 datasketch）
# ---------------------------------------------------------------------------

_MINHASH_NUM_HASHES = 20
_MINHASH_SHINGLE_SIZE = 3
_DEDUP_THRESHOLD = 0.85


def _compute_minhash(text: str) -> frozenset:
    """计算文本的 MinHash 签名（取最小的 N 个 3-gram hash 值）。

    Returns:
        frozenset，包含最小的 _MINHASH_NUM_HASHES 个 hash 值。
    """
    text = text.lower().strip()
    shingles = set()
    for i in range(len(text) - _MINHASH_SHINGLE_SIZE + 1):
        shingle = text[i:i + _MINHASH_SHINGLE_SIZE]
        h = int(hashlib.md5(shingle.encode('utf-8')).hexdigest(), 16)
        shingles.add(h)

    if not shingles:
        # 文本太短，用整体 hash
        h = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
        return frozenset([h])

    # 取最小的 N 个作为签名
    sorted_hashes = sorted(shingles)
    signature = sorted_hashes[:_MINHASH_NUM_HASHES]
    return frozenset(signature)


def _minhash_jaccard(sig_a: frozenset, sig_b: frozenset) -> float:
    """用 MinHash 签名估算 Jaccard 相似度。"""
    if not sig_a or not sig_b:
        return 0.0
    intersection = len(sig_a & sig_b)
    union = len(sig_a | sig_b)
    return intersection / union if union > 0 else 0.0


def dedup(pair: dict, existing_hashes: set) -> bool:
    """MinHash 近似去重。

    Args:
        pair: QAPair 字典，使用 query 字段计算签名。
        existing_hashes: 已有签名集合（frozenset 的 set），原地修改。

    Returns:
        True 表示重复（应丢弃），False 表示新样本（已加入 existing_hashes）。
    """
    query = pair.get('query', '')
    new_sig = _compute_minhash(query)

    for existing_sig in existing_hashes:
        sim = _minhash_jaccard(new_sig, existing_sig)
        if sim > _DEDUP_THRESHOLD:
            return True  # 重复

    # 不重复，加入集合
    existing_hashes.add(new_sig)
    return False


# ---------------------------------------------------------------------------
# PII 脱敏
# ---------------------------------------------------------------------------

def sanitize_pii(text: str) -> str:
    """脱敏处理：替换 IP、手机号、邮箱、路径、公司名为占位符。

    Args:
        text: 原始文本。

    Returns:
        脱敏后的文本。
    """
    text = _IP_RE.sub('[IP]', text)
    text = _PHONE_RE.sub('[PHONE]', text)
    text = _EMAIL_RE.sub('[EMAIL]', text)
    text = _WIN_PATH_RE.sub('[PATH]', text)
    text = _UNIX_PATH_RE.sub('[PATH]', text)
    text = _COMPANY_RE.sub('[COMPANY]', text)
    return text


# ---------------------------------------------------------------------------
# 批量处理工具
# ---------------------------------------------------------------------------

def load_existing_hashes(data_dir: str = 'D:/GIT/data/training_data/') -> set:
    """扫描 data_dir 下所有 .json 文件，计算 query 的 MinHash 签名集合。

    Args:
        data_dir: 训练数据目录。

    Returns:
        frozenset 的 set，用于 dedup()。
    """
    hashes = set()
    if not os.path.isdir(data_dir):
        return hashes

    pattern = os.path.join(data_dir, '**', '*.json')
    json_files = glob.glob(pattern, recursive=True)

    for fpath in json_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 支持列表或单条记录
            records = data if isinstance(data, list) else [data]
            for record in records:
                query = record.get('query', '')
                if query:
                    sig = _compute_minhash(query)
                    hashes.add(sig)
        except (json.JSONDecodeError, OSError):
            continue  # 跳过损坏文件

    return hashes


def process_pending_dir(
    pending_dir: str  = 'D:/GIT/data/distill_queue/completed/',
    train_pool_dir: str = 'D:/GIT/data/training_data/incremental/',
    threshold: float = 0.75,
) -> dict:
    """扫描 pending_dir，对每条记录去重+评分，通过则写入 train_pool_dir。

    Args:
        pending_dir:    待处理 JSON 文件目录。
        train_pool_dir: 通过质量门控后的输出目录。
        threshold:      质量评分通过阈值。

    Returns:
        统计字典 {"total", "passed", "rejected_dedup", "rejected_quality"}。
    """
    stats = {'total': 0, 'passed': 0, 'rejected_dedup': 0, 'rejected_quality': 0}

    if not os.path.isdir(pending_dir):
        return stats

    os.makedirs(train_pool_dir, exist_ok=True)

    existing_hashes = load_existing_hashes()
    pattern = os.path.join(pending_dir, '*.json')
    json_files = glob.glob(pattern)

    passed_records = []

    for fpath in json_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            records = data if isinstance(data, list) else [data]
        except (json.JSONDecodeError, OSError):
            continue

        for record in records:
            stats['total'] += 1

            # 1. 去重
            if dedup(record, existing_hashes):
                stats['rejected_dedup'] += 1
                continue

            # 2. 质量评分
            detail = score(record, threshold=threshold)
            if not detail['passed']:
                stats['rejected_quality'] += 1
                continue

            enriched = dict(record)
            enriched['score_detail'] = detail
            passed_records.append(enriched)
            stats['passed'] += 1

    # 写入通过的记录
    if passed_records:
        import time
        out_fname = f'batch_{int(time.time())}.json'
        out_path  = os.path.join(train_pool_dir, out_fname)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(passed_records, f, ensure_ascii=False, indent=2)

    return stats


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print('=' * 60)
    print('quality_gate.py 自测')
    print('=' * 60)

    # 测试数据 1：高质量 GRBL 配置回答
    pair1 = {
        'query': '如何设置 GRBL 的步进电机步数？',
        'answer': (
            '设置 GRBL 步进电机步数需要修改 $100/$101/$102 参数：\n\n'
            '1. 连接 GRBL 控制器，打开串口终端（波特率 115200）\n'
            '2. 输入 $100=800 设置 X 轴步数（800 步/mm）\n'
            '3. 输入 $101=800 设置 Y 轴步数\n'
            '4. 输入 $102=400 设置 Z 轴步数\n\n'
            '计算公式：步数/mm = (电机步数 × 细分) / 丝杆导程\n'
            '例如：200步 × 16细分 / 4mm = 800步/mm\n\n'
            '```\n$100=800\n$101=800\n$102=400\n```\n\n'
            '设置后输入 $$ 验证参数是否生效。'
        ),
        'intent': 'grbl_config',
        'source_backend': 'claude',
        'teacher_backends': ['claude', 'deepseek'],
        'all_answers': [
            '设置 $100=800 可以配置 X 轴步数，单位是步/mm。',
            '通过修改 $100/$101/$102 参数设置各轴步数，常见值为 800步/mm。',
        ],
    }

    # 测试数据 2：回答过短（低质量）
    pair2 = {
        'query': 'GRBL 最大速度怎么设置？',
        'answer': '设置 $110 参数。',
        'intent': 'grbl_config',
        'source_backend': 'deepseek',
        'teacher_backends': ['deepseek'],
        'all_answers': ['设置 $110 参数。'],
    }

    # 测试数据 3：含非法 GRBL 参数值
    pair3 = {
        'query': '如何配置 GRBL 归零速度？',
        'answer': (
            'GRBL 归零速度通过以下参数控制：\n\n'
            '1. $24=500 设置归零寻找速度（单位 mm/min）\n'
            '2. $25=2000 设置归零拉回速度（单位 mm/min）\n'
            '3. $27=5 设置归零拉回距离（单位 mm）\n\n'
            '注意：$24 的合法范围是 1-10000 mm/min，'
            '如果设置 $24=99999 会超出范围导致异常。\n\n'
            '```\n$24=500\n$25=2000\n$27=5\n```'
        ),
        'intent': 'grbl_homing',
        'source_backend': 'nvidia_nim',
        'teacher_backends': ['nvidia_nim', 'claude'],
        'all_answers': [
            '$24 控制归零寻找速度，$25 控制拉回速度，建议 $24=500 mm/min。',
            '归零速度参数：$24=500（寻找）, $25=2000（拉回）, $27=5（拉回距离）。',
        ],
    }

    test_pairs = [pair1, pair2, pair3]

    print('\n--- 单条评分测试 ---')
    for i, pair in enumerate(test_pairs, 1):
        detail = score(pair)
        print(f'\n[pair{i}] query: {pair["query"][:30]}...')
        print(f'  total={detail["total"]:.4f}  passed={detail["passed"]}')
        print(f'  accuracy={detail["accuracy"]:.4f}  completeness={detail["completeness"]:.4f}')
        print(f'  consistency={detail["consistency"]:.4f}  format={detail["format"]:.4f}')
        if detail['rejection_reason']:
            print(f'  rejection: {detail["rejection_reason"]}')

    print('\n--- 批量过滤测试 ---')
    passed, rejected = filter_batch(test_pairs)
    print(f'通过: {len(passed)} 条，拒绝: {len(rejected)} 条')
    for p in passed:
        print(f'  [PASS] {p["query"][:40]}')
    for r in rejected:
        print(f'  [FAIL] {r["query"][:40]} | {r["score_detail"]["rejection_reason"]}')

    print('\n--- PII 脱敏测试 ---')
    pii_text = (
        '联系深圳科技有限公司，邮箱 admin@example.com，'
        '电话 13812345678，服务器 192.168.1.100，'
        '日志路径 /home/user/logs/cnc.log 或 C:/Users/admin/data'
    )
    clean = sanitize_pii(pii_text)
    print(f'原文: {pii_text}')
    print(f'脱敏: {clean}')

    print('\n--- MinHash 去重测试 ---')
    hashes: set = set()
    q1 = {'query': '如何设置 GRBL 步进电机步数？'}
    q2 = {'query': '如何设置 GRBL 步进电机步数？'}
    q3 = {'query': 'CNC 主轴转速如何调节？'}

    r1 = dedup(q1, hashes)
    r2 = dedup(q2, hashes)
    r3 = dedup(q3, hashes)
    print(f'q1 重复={r1} (期望 False)')
    print(f'q2 重复={r2} (期望 True，与 q1 相同)')
    print(f'q3 重复={r3} (期望 False，不同问题)')

    print('\n自测完成。')
