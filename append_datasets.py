#!/usr/bin/env python3
"""
Download 4 HuggingFace datasets, convert to messages format,
deduplicate, and append to round5_training_data.json
"""

import json
import os
import sys

os.environ["HF_HOME"] = "D:/GIT/hf_cache"
os.environ["HF_DATASETS_CACHE"] = "D:/GIT/hf_cache"

from datasets import load_dataset

TARGET_FILE = "D:/GIT/round5_training_data.json"
MIN_CHARS = 50
MAX_CHARS = 2000
DEDUP_PREFIX = 80


def load_existing(path):
    if not os.path.exists(path):
        print(f"[INFO] {path} not found, starting fresh.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"[INFO] Loaded {len(data)} existing records from {path}")
    return data


def build_dedup_set(existing):
    seen = set()
    for item in existing:
        msgs = item.get("messages", [])
        if msgs:
            content = msgs[0].get("content", "")
            seen.add(content[:DEDUP_PREFIX])
    return seen


def is_valid(text, min_c=MIN_CHARS, max_c=MAX_CHARS):
    return isinstance(text, str) and min_c <= len(text.strip()) <= max_c


def make_pair(user_text, assistant_text):
    return {
        "messages": [
            {"role": "user", "content": user_text.strip()},
            {"role": "assistant", "content": assistant_text.strip()},
        ]
    }


# ── Dataset 1: MuratKomurcu/stm32-hal-dataset ──────────────────────────────
def process_stm32(seen):
    print("\n[1/4] Loading MuratKomurcu/stm32-hal-dataset ...")
    ds = load_dataset(
        "MuratKomurcu/stm32-hal-dataset",
        split="train",
        cache_dir="D:/GIT/hf_cache",
        trust_remote_code=True,
    )
    print(f"      Raw rows: {len(ds)}")
    pairs = []
    for row in ds:
        instruction = str(row.get("instruction") or "").strip()
        inp = str(row.get("input") or "").strip()
        output = str(row.get("output") or "").strip()
        user = (instruction + "\n" + inp).strip() if inp else instruction
        if not is_valid(user, MIN_CHARS) or not is_valid(output):
            continue
        key = user[:DEDUP_PREFIX]
        if key in seen:
            continue
        seen.add(key)
        pairs.append(make_pair(user, output))
    print(f"      New pairs added: {len(pairs)}")
    return pairs


# ── Dataset 2: bshada/arduino.stackexchange.com ────────────────────────────
def process_arduino(seen):
    print("\n[2/4] Loading bshada/arduino.stackexchange.com ...")
    ds = load_dataset(
        "bshada/arduino.stackexchange.com",
        split="train",
        cache_dir="D:/GIT/hf_cache",
        trust_remote_code=True,
    )
    print(f"      Raw rows: {len(ds)}")
    pairs = []
    for row in ds:
        title = str(row.get("Title") or "").strip()
        body = str(row.get("Body") or "").strip()
        answer = str(row.get("Answer") or "").strip()
        user = (title + "\n\n" + body).strip() if body else title
        if not is_valid(user, MIN_CHARS) or not is_valid(answer):
            continue
        key = user[:DEDUP_PREFIX]
        if key in seen:
            continue
        seen.add(key)
        pairs.append(make_pair(user, answer))
    print(f"      New pairs added: {len(pairs)}")
    return pairs


# ── Dataset 3: mlfoundations-dev/stackexchange_reverseengineering ──────────
def process_re(seen):
    print("\n[3/4] Loading mlfoundations-dev/stackexchange_reverseengineering ...")
    ds = load_dataset(
        "mlfoundations-dev/stackexchange_reverseengineering",
        split="train",
        cache_dir="D:/GIT/hf_cache",
        trust_remote_code=True,
    )
    print(f"      Raw rows: {len(ds)}")
    pairs = []
    for row in ds:
        # Try instruction/completion first, then conversations
        instruction = row.get("instruction") or ""
        completion = row.get("completion") or ""
        if instruction and completion:
            user = str(instruction).strip()
            assistant = str(completion).strip()
        elif row.get("conversations"):
            convs = row["conversations"]
            if isinstance(convs, list) and len(convs) >= 2:
                user = str(convs[0].get("value") or convs[0].get("content") or "").strip()
                assistant = str(convs[1].get("value") or convs[1].get("content") or "").strip()
            else:
                continue
        else:
            continue
        if not is_valid(user, MIN_CHARS) or not is_valid(assistant):
            continue
        key = user[:DEDUP_PREFIX]
        if key in seen:
            continue
        seen.add(key)
        pairs.append(make_pair(user, assistant))
    print(f"      New pairs added: {len(pairs)}")
    return pairs


# ── Dataset 4: Mxode/Chinese-StackOverflow-QA-C_Language ──────────────────
def process_chinese_c(seen):
    print("\n[4/4] Loading Mxode/Chinese-StackOverflow-QA-C_Language ...")
    ds = load_dataset(
        "Mxode/Chinese-StackOverflow-QA-C_Language",
        split="train",
        cache_dir="D:/GIT/hf_cache",
        trust_remote_code=True,
    )
    print(f"      Raw rows: {len(ds)}")
    pairs = []
    for row in ds:
        prompt = str(row.get("prompt") or "").strip()
        response = str(row.get("response") or "").strip()
        if not is_valid(prompt, MIN_CHARS) or not is_valid(response):
            continue
        key = prompt[:DEDUP_PREFIX]
        if key in seen:
            continue
        seen.add(key)
        pairs.append(make_pair(prompt, response))
    print(f"      New pairs added: {len(pairs)}")
    return pairs


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    existing = load_existing(TARGET_FILE)
    seen = build_dedup_set(existing)
    print(f"[INFO] Dedup set size (existing questions): {len(seen)}")

    all_new = []

    try:
        all_new.extend(process_stm32(seen))
    except Exception as e:
        print(f"[ERROR] stm32 dataset failed: {e}")

    try:
        all_new.extend(process_arduino(seen))
    except Exception as e:
        print(f"[ERROR] arduino dataset failed: {e}")

    try:
        all_new.extend(process_re(seen))
    except Exception as e:
        print(f"[ERROR] RE dataset failed: {e}")

    try:
        all_new.extend(process_chinese_c(seen))
    except Exception as e:
        print(f"[ERROR] Chinese C dataset failed: {e}")

    combined = existing + all_new
    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Total new pairs added : {len(all_new)}")
    print(f"New total in file     : {len(combined)}")
    print(f"Saved to              : {TARGET_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
