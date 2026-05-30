#!/usr/bin/env python3
"""
在线验证路由分类器 — 用真实 LLM 测试准确率
=============================================
使用你的 MCP 配置中的多个 LLM 来测试分类器的一致性。
"""

import json, os
from collections import Counter

# Load the zero-shot classifier prompt
CLASSIFIER_PROMPT = open("C:/Users/zhugu/Desktop/routing_classifier_prompt.txt", "r", encoding="utf-8").read()

# Load test cases
TEST_CASES = []

# Synthetic samples (known labels)
with open("C:/Users/zhugu/Desktop/routing_training_data.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        entry = json.loads(line.strip())
        TEST_CASES.append(("synthetic", entry["label"], entry["text"]))

# Adversarial samples
if os.path.exists("C:/Users/zhugu/Desktop/adversarial_test_set.jsonl"):
    with open("C:/Users/zhugu/Desktop/adversarial_test_set.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            TEST_CASES.append(("adversarial", entry["label"], entry["text"]))

print(f"Loaded {len(TEST_CASES)} test cases")


# ===== LOCAL VERIFICATION (no API needed) =====
def rule_based_classify(text: str) -> tuple:
    """Same classifier as train_router.py"""
    t = text.lower()

    # Absolute identity matches
    if "you are codex" in t and ("gpt-5" in t or "apply_patch" in t or "multi_tool_use.parallel" in t):
        return "codex", 1.0
    if "claude code" in t and "anthropic" in t:
        return "claude", 1.0
    if ("cursor ide" in t or "cursor cli" in t or
        "running as a coding agent in the cursor" in t):
        return "cursor", 1.0

    # Unique tool names (most reliable signal)
    signals = {
        "cursor": ["applypatch", "run_terminal_cmd", "read_lints", "todo_write",
                    "startline:endline:filepath", "anysphere"],
        "codex": ["multi_tool_use.parallel", "personality_pragmatic",
                   "personality_friendly", "codex_protocol", "config.toml"],
        "claude": ["enterplanmode", "enterworktree", "croncreate", "schedulewakeup",
                    "bypasspermissions", "claude.md", "settings.local.json"],
        "kiro": ["createexecutebashtool", "createreadfiletool", "invokesubagent",
                  "subagentresponse", "kiroagent", "aws-ipl", "langgraph",
                  "requirements-first workflow", "design-first workflow"],
    }

    scores = {}
    for tool, keywords in signals.items():
        scores[tool] = sum(1 for k in keywords if k in t)

    max_score = max(scores.values())
    if max_score > 0:
        winner = [k for k, v in scores.items() if v == max_score][0]
        # Check if there's a tie
        ties = [k for k, v in scores.items() if v == max_score]
        if len(ties) > 1:
            return "uncertain", 0.0
        return winner, min(0.95, 0.5 + max_score * 0.15)

    # Unique phrases (medium signal)
    phrase_signals = {
        "codex": ["cheerleading", "fluff", "epistemically curious"],
        "claude": ["compaction retry", "system-reminder"],
        "cursor": ["computer use agent", "root orchestrator agent"],
        "kiro": ["bugfix workflow", "spec creation", "kiro agent"],
    }
    for tool, phrases in phrase_signals.items():
        if any(p in t for p in phrases):
            return tool, 0.7

    # File/directory references (medium signal)
    if ".claude/" in t or "claude.md" in t:
        return "claude", 0.8
    if ".codex/" in t or "config.toml" in t:
        return "codex", 0.8
    if ".kiro/" in t or "aws-ipl" in t:
        return "kiro", 0.8

    return "uncertain", 0.0


def verify():
    """Run all test cases and compute accuracy."""
    results = {"cursor": [], "codex": [], "claude": [], "kiro": []}
    confusion = Counter()
    total, correct, uncertain = 0, 0, 0

    for source, true_label, text in TEST_CASES:
        pred_label, confidence = rule_based_classify(text[:500])
        confusion[(true_label, pred_label)] += 1
        total += 1
        if pred_label == true_label:
            correct += 1
        if pred_label == "uncertain":
            uncertain += 1
        results[true_label].append((pred_label, confidence, source))

    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS (Rule-Based Classifier)")
    print("=" * 60)

    # Per-class accuracy
    for label in ["cursor", "codex", "claude", "kiro"]:
        class_results = results[label]
        class_correct = sum(1 for p, c, s in class_results if p == label)
        class_total = len(class_results)
        if class_total > 0:
            print(f"  {label}: {class_correct}/{class_total} = {class_correct/class_total:.0%}")

    print(f"\nOverall: {correct}/{total} = {correct/total:.2%}")
    print(f"Uncertain (needs more context): {uncertain}")

    # Confusion matrix
    print("\n" + "=" * 60)
    print("CONFUSION MATRIX")
    print("=" * 60)
    labels = ["cursor", "codex", "claude", "kiro", "uncertain"]
    header = "           " + "  ".join(f"{l:>8}" for l in labels)
    print(header)
    for true_l in ["cursor", "codex", "claude", "kiro"]:
        row = f"{true_l:>10}  "
        for pred_l in labels:
            row += f"{confusion[(true_l, pred_l)]:>8}  "
        print(row)

    # Show errors
    errors = [(true, pred, conf, text)
              for true, results_list in results.items()
              for pred, conf, src in results_list
              if pred != true and pred != "uncertain"]
    if errors:
        print(f"\n=== ERRORS ({len(errors)}) ===")
        for true, pred, conf, text in errors[:10]:
            print(f"  TRUE={true} PRED={pred} CONF={conf:.0%}")
            print(f"    {text[:150]}...")

    return correct / total if total > 0 else 0


if __name__ == "__main__":
    accuracy = verify()

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    if accuracy >= 0.95:
        print("[PASS] Rule-based classifier is production-ready")
    elif accuracy >= 0.85:
        print("[WARN] Good but needs ML fallback for edge cases")
    else:
        print("[FAIL] Needs more training data or feature engineering")

    print("\nTo test with real LLMs, use the MCP tools:")
    print("  Classifier prompt is in: routing_classifier_prompt.txt")
    print("  Test cases are in: adversarial_test_set.jsonl")
