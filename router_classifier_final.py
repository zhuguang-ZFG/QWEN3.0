"""
AI Coding Tool Router — Production Classifier
No external dependencies. Pure Python. Drop-in for any routing system.
"""

import json, os
from collections import Counter

# ============================================================
# COMPLETE SIGNAL DICTIONARY (from binary reverse engineering)
# ============================================================
SIGNALS = {
    "cursor": {
        # Identity lines (100% signal)
        "identity": [
            "cursor ide", "cursor cli", "running as a coding agent in the cursor",
            "anysphere",
        ],
        # Unique tool names (99% signal)
        "tools": [
            "applypatch", "run_terminal_cmd", "read_lints", "todo_write",
            "startline:endline:filepath",
        ],
        # Formatting quirks
        "format": [
            "Lxxx:LINE_CONTENT",
            "producing plain text that will later be styled by cursor",
        ],
        # Agent types
        "agents": [
            "computer use agent", "root orchestrator agent in the cursor ide",
            "background agent", "coding agent in the cursor ide",
        ],
        # Stream protocol
        "stream": ["text/event-stream", "[DONE]", "message_start", "message_stop"],
    },
    "codex": {
        "identity": [
            "you are codex", "gpt-5", "codex_protocol", "openai",
            "codex cli is an open source project",
        ],
        "tools": [
            "multi_tool_use.parallel", "apply_patch",
            "rg --files", "codex-run-as",
        ],
        "format": [
            "cheerleading", "motivational language", "fluff",
            "epistemically curious collaborator",
            "clarity", "pragmatism", "rigor",
        ],
        "personality": [
            "personality_friendly", "personality_pragmatic",
            "vivid inner life as codex",
            "deeply pragmatic, effective software engineer",
        ],
        "stream": [
            "message_chunk", "reasoning_content_delta",
            "turnnotsteerable", "dynamic_tool_call",
        ],
        "config": ["config.toml", ".codex/", "agents.md"],
    },
    "claude": {
        "identity": [
            "claude code", "anthropic", "claude agent sdk",
            "anthropic's official cli",
        ],
        "tools": [
            " enterplanmode", " enterworktree", " exitworktree",
            " croncreate", " cronlist", " crondelete",
            " schedulewakeup", " askuserquestion",
            " teamcreate", " teamdelete", " sendmessage",
            " notebookedit", " lsp ",
            " taskcreate", " taskupdate", " tasklist",
            " glob ", " grep ", " edit ", " write ", " read ",
            " skill ",
            " tool_use", "content_block",
            "claude.md", "memory.md",
        ],
        "format": [
            "system-reminder", "compaction retry",
            "claude.md", "memory.md",
            "content_block_start", "content_block_delta",
        ],
        "config": [
            ".claude/", "settings.local.json", "bypasspermissions",
            "alwaysallow", "alwaysdeny",
            "anthropic_api_key",
        ],
        "stream": [
            "text_delta", "input_json_delta", "redacted_thinking",
            "message_start", "content_block_stop",
        ],
    },
    "kiro": {
        "identity": [
            "createexecutebashtool", "createreadfiletool",
            "createwritefiletool", "creategrepsearchtool",
            "createfilesearchtool", "createlistdirectorytool",
            "createinvokesubagenttool", "createstrreplacetool",
            "invokesubagent", "subagentresponse",
            "kiroagent", "aws-ipl", "amazon",
            "langchain", "langgraph",
        ],
        "tools": [
            "createexecutebashtool", "createreadfiletool",
            "createwritefiletool", "creategrepsearchtool",
            "createfilesearchtool", "createlistdirectorytool",
            "createinvokesubagenttool",
        ],
        "format": [
            "requirements-first workflow", "design-first workflow",
            "bugfix workflow", "spec creation",
            "bug condition methodology",
        ],
        "agents": [
            "spec task execution subagent",
            "spec orchestrator",
            "custom agents for kiro",
            "you are a specialized subagent",
        ],
        "stream": [
            "agent_thought_chunk", "agent_message_chunk",
            "agent_action", "agent_end",
            "lc_prefer_streaming", "on_chat_model_stream",
        ],
        "config": [".kiro/", "kiroagent.modelselection", "trustedcommands"],
    },
}


def classify(text: str, min_confidence: float = 0.5) -> tuple:
    """
    Classify a system prompt text into one of: cursor, codex, claude, kiro, uncertain.
    Returns (label, confidence, evidence).
    """
    t = text.lower()

    # Focus on first 500 chars where system prompt identity lives
    # Also search whole text for tool names (which can appear anywhere)
    t_head = t[:500]

    # Detect if this is likely a user query (not a system prompt)
    is_likely_user_query = (
        not t_head.strip().startswith("you are") and
        not any(kw in t_head for kw in ["tool", "agent", "running as", "you have access",
                                          "applypatch", "run_terminal_cmd", "multi_tool_use",
                                          "createexecut", "enterplanmode", "croncreate"])
    )
    if is_likely_user_query:
        return "not_system_prompt", 0.0, ["detected_user_query"]

    scores = {}
    evidence = {}

    for tool, categories in SIGNALS.items():
        tool_score = 0
        tool_evidence = []
        for category, keywords in categories.items():
            # Category weight: identity > tools > everything else
            weight = 3.0 if category == "identity" else 2.0 if category == "tools" else 1.0
            for kw in keywords:
                if kw in t:
                    tool_score += weight
                    tool_evidence.append(f"{category}:{kw}")

        scores[tool] = tool_score
        evidence[tool] = tool_evidence

    max_score = max(scores.values())

    # No signals at all
    if max_score == 0:
        return "uncertain", 0.0, []

    # Find winner(s)
    winners = [tool for tool, score in scores.items() if score == max_score]

    # Tie-breaking: prefer identity matches
    if len(winners) > 1:
        for tool in winners:
            if evidence[tool] and any(e.startswith("identity:") for e in evidence[tool]):
                # This winner has identity evidence
                conf = min(0.95, 0.6 + max_score * 0.1)
                return tool, conf, evidence[tool]

    # Single winner
    winner = winners[0]

    # Confidence calculation
    if max_score >= 6:  # Strong signal (identity + tools)
        conf = 0.95
    elif max_score >= 3:  # Moderate
        conf = 0.75
    elif max_score >= 1:  # Weak
        conf = 0.5
    else:
        conf = 0.0

    if conf < min_confidence:
        return "uncertain", conf, evidence[winner]

    return winner, conf, evidence[winner]


def batch_classify(texts: list) -> list:
    """Classify multiple texts."""
    return [classify(t) for t in texts]


# ============================================================
# EVALUATION
# ============================================================
def evaluate(test_file: str):
    """Evaluate classifier on a JSONL test set."""
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return

    test_cases = []
    with open(test_file, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line.strip())
            test_cases.append((entry['label'], entry['text']))

    results = {"correct": 0, "wrong": 0, "uncertain": 0, "total": len(test_cases)}
    confusion = Counter()
    errors = []

    for true_label, text in test_cases:
        pred_label, conf, ev = classify(text[:500], min_confidence=0.4)

        if pred_label == "uncertain":
            results["uncertain"] += 1
        elif pred_label == true_label:
            results["correct"] += 1
        else:
            results["wrong"] += 1
            errors.append((true_label, pred_label, conf, text[:150]))

        confusion[(true_label, pred_label)] += 1

    # Print report
    print("=" * 60)
    print("CLASSIFIER EVALUATION")
    print("=" * 60)
    print(f"Total: {results['total']}")
    print(f"Correct: {results['correct']} ({results['correct']/results['total']:.1%})")
    print(f"Wrong: {results['wrong']} ({results['wrong']/results['total']:.1%})")
    print(f"Uncertain: {results['uncertain']} ({results['uncertain']/results['total']:.1%})")

    # Accuracy excl uncertain
    decided = results['correct'] + results['wrong']
    if decided > 0:
        print(f"Accuracy (when decided): {results['correct']}/{decided} = {results['correct']/decided:.1%}")

    # Confusion matrix
    print("\nConfusion Matrix:")
    labels = ["cursor", "codex", "claude", "kiro", "uncertain"]
    header = "           " + "  ".join(f"{l:>8}" for l in labels)
    print(header)
    for true_l in ["cursor", "codex", "claude", "kiro"]:
        row = f"{true_l:>10}  "
        for pred_l in labels:
            row += f"{confusion[(true_l, pred_l)]:>8}  "
        print(row)

    # Show errors
    if errors:
        print(f"\nERRORS ({len(errors)}):")
        for true, pred, conf, text in errors[:10]:
            print(f"  TRUE={true} -> PRED={pred} (conf={conf:.0%})")
            print(f"    {text}...")

    return results


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Predict mode
        text = " ".join(sys.argv[1:])
        label, conf, evidence = classify(text)
        print(f"Label: {label}")
        print(f"Confidence: {conf:.0%}")
        if evidence:
            print(f"Evidence: {evidence[:5]}")
    else:
        # Evaluate on all available test sets
        for test_file in [
            "C:/Users/zhugu/Desktop/combined_training_data.jsonl",
            "C:/Users/zhugu/Desktop/adversarial_test_set.jsonl",
        ]:
            if os.path.exists(test_file):
                print(f"\n{'='*60}")
                print(f"Test set: {test_file}")
                print(f"{'='*60}")
                evaluate(test_file)

        # Interactive demo
        print("\n" + "=" * 60)
        print("INTERACTIVE DEMO")
        print("=" * 60)
        demos = [
            "You are gpt-4o. You are running as a coding agent in the Cursor IDE. Use ApplyPatch and run_terminal_cmd.",
            "You are Codex, a coding agent based on GPT-5. Use multi_tool_use.parallel and rg --files.",
            "You are Claude Code, Anthropic's official CLI for Claude. Use Glob, Grep, and EnterPlanMode.",
            "You are a helpful assistant. Use createExecuteBashTool to run commands.",
        ]
        for d in demos:
            label, conf, ev = classify(d)
            print(f"\n  Text: {d[:80]}...")
            print(f"  -> {label} ({conf:.0%})")
