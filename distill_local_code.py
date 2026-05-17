#!/usr/bin/env python3
"""
Distill local Python source code into high-quality Chinese Q&A pairs.
Scans D:/GIT for real programs (50-500 lines), calls Claude API to generate
5-8 Q&A pairs per file covering architecture, functions, patterns, issues, usage.
Output format: {"messages": [{"role": "user", ...}, {"role": "assistant", ...}]}
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ============================================================
# CONFIGURATION
# ============================================================
SCAN_DIR = r"D:\GIT"
OUTPUT_FILE = r"D:\GIT\local_code_distilled.json"
CHECKPOINT_FILE = r"D:\GIT\local_code_checkpoint.json"

API_URL = "https://right.codes/claude-aws/v1/messages"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
RATE_LIMIT_SECONDS = 0.5
CHECKPOINT_EVERY = 5

MIN_LINES = 50
MAX_LINES = 500

# Files to skip (training data, data files, this script itself)
SKIP_PATTERNS = [
    "train_", "training_", "distill_", "prepare_", "collect_",
    "extract_", "append_", "clean_", "generate_dpo", "grpo_train",
    "lora_merge", "validate_model", "evaluate_model", "test_model",
    "jailbreak", "uncensored", "reverse_engineering", "scrape_",
    "integrate_claude", "multi_turn_training", "prepare_round",
    "system_prompt_final", "opus_level_prompt", "synthesize_prompts",
    "distill_local_code",  # skip self
]

SYSTEM_PROMPT = """你是一位资深Python工程师。请分析以下代码，生成5-8个高质量的中文问答对，涵盖：代码架构、关键函数功能、设计模式、潜在问题、使用方法。

每个问答对严格按照以下格式输出，每对之间用空行分隔：
Q: <问题>
A: <回答>

要求：
1. 问题要具体，针对代码中的实际内容
2. 回答要详细准确，包含代码细节、参数、逻辑
3. 覆盖不同角度：整体架构、核心函数、设计选择、潜在bug、实际用法
4. 使用中文，技术术语可保留英文
5. 每个回答100-400字"""


# ============================================================
# FILE SCANNING
# ============================================================

def should_skip(filename: str) -> bool:
    """Return True if this file should be excluded."""
    name = filename.lower()
    for pattern in SKIP_PATTERNS:
        if pattern in name:
            return True
    return False


def count_lines(filepath: str) -> int:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def scan_python_files(scan_dir: str) -> list[dict]:
    """Scan for Python files between MIN_LINES and MAX_LINES, not in skip list."""
    candidates = []
    scan_path = Path(scan_dir)

    # Only scan root level (maxdepth 1 equivalent)
    for py_file in scan_path.glob("*.py"):
        if should_skip(py_file.name):
            continue
        lines = count_lines(str(py_file))
        if MIN_LINES <= lines <= MAX_LINES:
            candidates.append({
                "path": str(py_file),
                "name": py_file.name,
                "lines": lines,
            })

    # Also scan one level of subdirectories for interesting programs
    for subdir in scan_path.iterdir():
        if subdir.is_dir() and not subdir.name.startswith('.'):
            for py_file in subdir.glob("*.py"):
                if should_skip(py_file.name):
                    continue
                lines = count_lines(str(py_file))
                if MIN_LINES <= lines <= MAX_LINES:
                    candidates.append({
                        "path": str(py_file),
                        "name": f"{subdir.name}/{py_file.name}",
                        "lines": lines,
                    })

    candidates.sort(key=lambda x: x["lines"], reverse=True)
    return candidates


def read_file_content(filepath: str) -> str:
    """Read file, truncate to ~8000 chars to stay within token budget."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        if len(content) > 8000:
            content = content[:8000] + "\n\n# [文件已截断，仅显示前8000字符]"
        return content
    except Exception as e:
        return f"# 读取失败: {e}"


# ============================================================
# CHECKPOINT
# ============================================================

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"processed": [], "results": []}


def save_checkpoint(checkpoint: dict):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ============================================================
# CLAUDE API CALL
# ============================================================

def call_claude(file_name: str, code: str) -> str | None:
    """Send code to Claude, return raw text response."""
    api_key = os.environ.get("CLAUDE_API_KEY", "")
    if not api_key:
        print("  ERROR: CLAUDE_API_KEY not set")
        return None

    user_prompt = f"文件名: {file_name}\n\n```python\n{code}\n```"

    payload = json.dumps({
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  API Error: {e}")
        return None


# ============================================================
# PARSE Q&A PAIRS
# ============================================================

def parse_qa_pairs(text: str) -> list[dict]:
    """
    Parse Claude response into list of {"q": ..., "a": ...} dicts.
    Handles format:  Q: ...\nA: ...
    """
    if not text:
        return []

    pairs = []
    # Split on Q: markers
    blocks = re.split(r'\n(?=Q[:：])', text.strip())

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Match Q: ... A: ... pattern (A can be on same or next line)
        m = re.match(
            r'Q[:：]\s*(.+?)\s*\n+A[:：]\s*([\s\S]+)',
            block,
            re.DOTALL
        )
        if m:
            question = m.group(1).strip()
            answer = m.group(2).strip()
            # Trim answer at next Q: if present
            answer = re.split(r'\nQ[:：]', answer)[0].strip()
            if question and answer and len(answer) > 20:
                pairs.append({"q": question, "a": answer})

    return pairs


def qa_to_messages(pairs: list[dict], source_file: str) -> list[dict]:
    """Convert Q&A pairs to training message format."""
    records = []
    for pair in pairs:
        records.append({
            "messages": [
                {"role": "user", "content": pair["q"]},
                {"role": "assistant", "content": pair["a"]},
            ],
            "source": source_file,
        })
    return records


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  Local Code Distillation → Chinese Q&A Pairs")
    print("=" * 60)

    # Scan for candidate files
    print(f"\nScanning {SCAN_DIR} for Python files ({MIN_LINES}-{MAX_LINES} lines)...")
    candidates = scan_python_files(SCAN_DIR)
    print(f"Found {len(candidates)} candidate files:")
    for c in candidates:
        print(f"  {c['lines']:>4} lines  {c['name']}")

    if not candidates:
        print("No candidates found. Exiting.")
        return

    # Load checkpoint
    checkpoint = load_checkpoint()
    processed_set = set(checkpoint.get("processed", []))
    results = checkpoint.get("results", [])
    print(f"\nAlready processed: {len(processed_set)} files")
    print(f"Existing Q&A pairs: {len(results)}")

    to_process = [c for c in candidates if c["path"] not in processed_set]
    print(f"Remaining: {len(to_process)} files\n")

    if not to_process:
        print("All files already processed.")
    else:
        for i, candidate in enumerate(to_process):
            filepath = candidate["path"]
            name = candidate["name"]
            lines = candidate["lines"]

            print(f"[{i+1}/{len(to_process)}] {name} ({lines} lines)...", end=" ", flush=True)

            code = read_file_content(filepath)
            response = call_claude(name, code)

            if response:
                pairs = parse_qa_pairs(response)
                if pairs:
                    new_records = qa_to_messages(pairs, filepath)
                    results.extend(new_records)
                    checkpoint["processed"].append(filepath)
                    print(f"OK — {len(pairs)} Q&A pairs")
                else:
                    print(f"PARSE_FAILED (response: {response[:80]!r})")
                    checkpoint["processed"].append(filepath)  # skip on retry
            else:
                print("API_FAILED — will retry next run")

            # Checkpoint every N files
            if (i + 1) % CHECKPOINT_EVERY == 0:
                checkpoint["results"] = results
                save_checkpoint(checkpoint)
                print(f"  [checkpoint] {len(results)} total pairs saved")

            if i < len(to_process) - 1:
                time.sleep(RATE_LIMIT_SECONDS)

    # Final save
    checkpoint["results"] = results
    save_checkpoint(checkpoint)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  Done! Total Q&A pairs: {len(results)}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Checkpoint: {CHECKPOINT_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()



