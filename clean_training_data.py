#!/usr/bin/env python3
"""Clean training data: remove low-quality, duplicates, refusal patterns."""

import json, re, os, sys, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

MORALIZING = [
    "text-based AI", "please refrain", "unethical", "derogatory",
    "inappropriate", "offensive", "racist", "discrimin", "unacceptable",
    "cannot fulfill", "ethical guideline", "against my programming",
    "cannot provide", "not able to", "as an AI", "as a language model",
    "I cannot", "sorry, I", "抱歉，我", "作为AI", "作为人工智能",
    "我不能", "我无法", "根据我的编程", "这违反", "不安全",
    "不符合道德", "建议咨询", "请谨慎"
]

def is_refusal(text: str) -> bool:
    text_lower = text.lower()
    return any(m.lower() in text_lower for m in MORALIZING)

def is_low_quality(item: dict) -> bool:
    msgs = item.get("messages", [])
    if len(msgs) < 2: return True
    user = msgs[0].get("content", "")
    assistant = msgs[1].get("content", "")

    # Too short (relaxed)
    if len(assistant) < 15: return True
    # Pure garbage
    if len(set(assistant)) < 5: return True
    return False

def is_duplicate(item: dict, seen: set) -> bool:
    msgs = item.get("messages", [])
    key = "..."
    for m in msgs:
        key = m.get("content","")[:80]
    h = hashlib.md5(key.encode()).hexdigest()
    if h in seen: return True
    seen.add(h)
    return False

def main():
    data_file = r"D:\GIT\round5_training_data.json"
    print(f"Loading {data_file}...")
    data = json.load(open(data_file, 'r', encoding='utf-8'))

    before = len(data)
    seen = set()
    cleaned = []

    for item in data:
        if is_low_quality(item): continue
        if is_refusal(item.get("messages",[{}])[1].get("content","")): continue
        if is_duplicate(item, seen): continue
        cleaned.append(item)

    print(f"Before: {before}, After: {len(cleaned)}, Removed: {before-len(cleaned)}")
    print(f"Removal rate: {(before-len(cleaned))/before*100:.1f}%")

    if len(cleaned) < before * 0.7:
        print("WARNING: More than 30% removed, check quality filters!")

    json.dump(cleaned, open(data_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"Cleaned data saved")

if __name__ == "__main__":
    main()
