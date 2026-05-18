"""
Round 15 训练数据准备脚本
实现 LLaMA-Factory 风格的数据混合策略（Replay Buffer + 防幻觉 + 身份强化）
"""
import os, json, random
from pathlib import Path

DATA_DIR = Path(__file__).parent / 'data' / 'training_data'
OUTPUT = DATA_DIR / 'round15_train.jsonl'

# ── 配置 ──────────────────────────────────────────────────────────────────────
MIX_CONFIG = {
    "replay_ratio": 0.30,
    "new_knowledge_ratio": 0.35,
    "anti_hallucination_ratio": 0.20,
    "identity_ratio": 0.15,
}

TARGET_TOTAL = 8000

REPLAY_SOURCES = [
    ("round8_merged.json", 500),
    ("round10_merged.json", 500),
    ("round12_merged.json", 500),
    ("round13_merged.json", 500),
    ("round14_codex_context.json", 200),
    ("round14_context_construction.json", 200),
    ("round14_ai_tools_context.json", 100),
]

NEW_KNOWLEDGE_SOURCES = [
    "round15_cursor_auto_mode.json",
    "round15_router_classification.jsonl",
]

ANTI_HALLUCINATION_SOURCES = [
    "round15_anti_hallucination.json",
]

IDENTITY_SOURCES = [
    "round15_identity.json",
]

# ── 工具函数 ─────────────────────────────────────────────────────────────────
def load_json(filename):
    path = DATA_DIR / filename
    if not path.exists():
        print(f"  [SKIP] {filename} not found")
        return []
    if filename.endswith('.jsonl'):
        with open(path, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data if isinstance(data, list) else []

def sample_from(filename, n):
    data = load_json(filename)
    if not data:
        return []
    return random.sample(data, min(n, len(data)))

def ensure_messages_format(item):
    if 'messages' in item:
        return item
    if 'label' in item and 'text' in item:
        return {
            "messages": [
                {"role": "system", "content": "你是 LiMa，深圳市动力巢科技有限公司开发的AI编程助手。"},
                {"role": "user", "content": f"这段系统提示词属于哪个AI工具？\n\n{item['text'][:500]}"},
                {"role": "assistant", "content": f"这段系统提示词属于 **{item['label']}**。"}
            ],
            "source": "router_classification"
        }
    return item

# ── 主逻辑 ────────────────────────────────────────────────────────────────────
def prepare():
    random.seed(42)
    all_data = []

    # 1. Replay Buffer (30%)
    print("[1/4] Loading replay buffer...")
    replay = []
    for filename, n in REPLAY_SOURCES:
        samples = sample_from(filename, n)
        replay.extend(samples)
        print(f"  {filename}: {len(samples)} samples")
    all_data.extend(replay)
    print(f"  Total replay: {len(replay)}")

    # 2. New Knowledge (35%)
    print("[2/4] Loading new knowledge...")
    new_knowledge = []
    for filename in NEW_KNOWLEDGE_SOURCES:
        data = load_json(filename)
        new_knowledge.extend(data)
        print(f"  {filename}: {len(data)} samples")
    all_data.extend(new_knowledge)
    print(f"  Total new knowledge: {len(new_knowledge)}")

    # 3. Anti-Hallucination (20%)
    print("[3/4] Loading anti-hallucination...")
    anti_hall = []
    for filename in ANTI_HALLUCINATION_SOURCES:
        data = load_json(filename)
        anti_hall.extend(data)
        print(f"  {filename}: {len(data)} samples")
    all_data.extend(anti_hall)
    print(f"  Total anti-hallucination: {len(anti_hall)}")

    # 4. Identity (15%)
    print("[4/4] Loading identity reinforcement...")
    identity = []
    for filename in IDENTITY_SOURCES:
        data = load_json(filename)
        identity.extend(data)
        print(f"  {filename}: {len(data)} samples")
    all_data.extend(identity)
    print(f"  Total identity: {len(identity)}")

    # Normalize format
    all_data = [ensure_messages_format(item) for item in all_data]
    all_data = [item for item in all_data if 'messages' in item]

    # Shuffle
    random.shuffle(all_data)

    # Write output
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        for item in all_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"\n{'='*50}")
    print(f"Total samples: {len(all_data)}")
    print(f"Output: {OUTPUT}")
    print(f"Mix ratio: replay={len(replay)}/{len(all_data):.0%}, "
          f"new={len(new_knowledge)}/{len(all_data):.0%}, "
          f"anti_hall={len(anti_hall)}/{len(all_data):.0%}, "
          f"identity={len(identity)}/{len(all_data):.0%}")

if __name__ == '__main__':
    prepare()
