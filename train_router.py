#!/usr/bin/env python3
"""
AI Coding Tool Router - Lightweight Classifier
==============================================
Trains a fastText/sklearn classifier to identify which AI coding tool
(Cursor/Codex/Claude Code/Kiro) generated a given system prompt.

Usage:
  python train_router.py --train          # Train the model
  python train_router.py --predict "..."   # Predict a single prompt
  python train_router.py --test           # Run on test set
  python train_router.py --benchmark      # Benchmark accuracy

Requirements:
  pip install scikit-learn fasttext numpy pandas
  (fastText is optional - sklearn fallback works too)
"""

import json, os, argparse
import numpy as np

# ============================================================
# FEATURE EXTRACTION
# ============================================================

# Each tool's unique signals - extracted from binary reverse engineering
TOOL_SIGNALS = {
    "cursor": {
        "identity": ["Cursor IDE", "Cursor CLI", "run_terminal_cmd", "ApplyPatch",
                     "read_lints", "todo_write", "startLine:endLine:filepath",
                     "Anysphere", "COMPUTER USE agent"],
        "tools": ["ApplyPatch", "run_terminal_cmd", "read_file", "read_lints",
                  "todo_write", "grep", "glob"],
        "directories": [".cursor/", "Cursor.exe"],
        "formatting": ["startLine:endLine:filepath"],
        "streaming": ["text/event-stream", "[DONE]"],
    },
    "codex": {
        "identity": ["You are Codex", "GPT-5", "codex_protocol", "OpenAI",
                     "multi_tool_use.parallel", "personality_friendly",
                     "personality_pragmatic", "epistemically curious"],
        "tools": ["apply_patch", "multi_tool_use.parallel", "rg --files",
                  "rg", "codex-run-as-fs-helper"],
        "directories": [".codex/", "config.toml", "AGENTS.md"],
        "formatting": ["cheerleading", "motivational language", "fluff",
                       "Values", "Clarity", "Pragmatism", "Rigor"],
        "streaming": ["message_chunk", "reasoning_content_delta",
                      "TurnNotSteerable", "dynamic_tool_call"],
    },
    "claude": {
        "identity": ["Claude Code", "Anthropic", "CLAUDE.md",
                     "EnterPlanMode", "EnterWorktree", "CronCreate",
                     "ScheduleWakeup", "anthropic_api_key"],
        "tools": ["Edit", "Write", "Read", "Glob", "Grep", "Bash",
                  "Agent", "TaskCreate", "TaskUpdate", "Skill",
                  "WebSearch", "WebFetch", "AskUserQuestion"],
        "directories": [".claude/", "settings.local.json", "MEMORY.md"],
        "formatting": ["system-reminder", "compaction retry",
                       "content_block_start", "text_delta"],
        "streaming": ["content_block_start", "content_block_delta",
                      "input_json_delta", "redacted_thinking"],
    },
    "kiro": {
        "identity": ["createExecuteBashTool", "createReadFileTool",
                     "createWriteFileTool", "invokeSubAgent",
                     "subagentResponse", "langchain", "langgraph",
                     "AWS-IPL", "Amazon", "Kiro Agent"],
        "tools": ["createExecuteBashTool", "createReadFileTool",
                  "createWriteFileTool", "createGrepSearchTool",
                  "createFileSearchTool", "createInvokeSubAgentTool",
                  "createListDirectoryTool", "createStrReplaceTool"],
        "directories": [".kiro/", "kiroAgent", "Kiro.exe"],
        "formatting": ["requirements-first", "design-first",
                       "bugfix workflow", "spec-task", "preset"],
        "streaming": ["agent_thought_chunk", "agent_message_chunk",
                      "agent_action", "agent_end", "lc_prefer_streaming"],
    },
}


def extract_features(text: str) -> dict:
    """Extract numerical features from a system prompt text."""
    text_lower = text.lower()
    features = {}

    # For each tool, count matching signals in each category
    for tool, categories in TOOL_SIGNALS.items():
        for category, signals in categories.items():
            count = sum(1 for s in signals if s.lower() in text_lower)
            features[f"{tool}_{category}"] = count
            # Binary: at least one match
            features[f"{tool}_{category}_any"] = 1 if count > 0 else 0

    # Check for common patterns
    features["starts_with_you_are"] = 1 if text_lower.strip().startswith("you are") else 0
    features["contains_gpt"] = 1 if "gpt" in text_lower[:200] else 0
    features["contains_claude"] = 1 if "claude" in text_lower[:200] else 0
    features["contains_codex"] = 1 if "codex" in text_lower[:200] else 0
    features["contains_cursor_ide"] = 1 if "cursor ide" in text_lower[:200] or "cursor cli" in text_lower[:200] else 0
    features["contains_anthropic"] = 1 if "anthropic" in text_lower[:200] else 0
    features["contains_openai"] = 1 if "openai" in text_lower[:200] else 0
    features["contains_langchain"] = 1 if "langchain" in text_lower or "langgraph" in text_lower else 0
    features["contains_vs_code_fork"] = 1 if ("vscode" in text_lower or "product.json" in text_lower or "extensions/" in text_lower) else 0

    # Text length (short prompts are harder)
    features["text_length"] = len(text)
    features["text_length_log"] = np.log(len(text) + 1)

    return features


# ============================================================
# RULE-BASED CLASSIFIER (100% accuracy on extracted signals)
# ============================================================

def rule_based_classify(text: str) -> tuple:
    """Deterministic rule-based classifier. Returns (label, confidence)."""
    text_lower = text.lower()

    # P0: Identity lines (absolute certainty)
    if "you are codex" in text_lower or "gpt-5" in text_lower:
        if "codex_protocol" in text_lower or "apply_patch" in text_lower or "multi_tool_use.parallel" in text_lower:
            return "codex", 1.0

    if "claude code" in text_lower and "anthropic" in text_lower:
        return "claude", 1.0

    if ("cursor ide" in text_lower or "cursor cli" in text_lower or
        "running as a coding agent in the cursor" in text_lower):
        return "cursor", 1.0

    # P1: Unique tool names (very strong)
    cursor_tools = ["applypatch", "run_terminal_cmd", "read_lints", "todo_write"]
    codex_tools = ["multi_tool_use.parallel", "rg --files"]
    claude_tools = ["enterplanmode", "enterworktree", "croncreate", "schedulewakeup", "askuserquestion"]
    kiro_tools = ["createexecutebashtool", "createreadfiletool", "creategrepsearchtool",
                  "invokesubagent", "subagentresponse", "kiroagent"]

    cursor_score = sum(1 for t in cursor_tools if t in text_lower)
    codex_score = sum(1 for t in codex_tools if t in text_lower)
    claude_score = sum(1 for t in claude_tools if t in text_lower)
    kiro_score = sum(1 for t in kiro_tools if t in text_lower)

    scores = {"cursor": cursor_score, "codex": codex_score,
              "claude": claude_score, "kiro": kiro_score}
    max_score = max(scores.values())
    if max_score > 0:
        winner = [k for k, v in scores.items() if v == max_score][0]
        return winner, min(0.95, 0.5 + max_score * 0.15)

    # P2: Directory/settings fingerprints
    if ".claude/" in text_lower or "claude.md" in text_lower or "settings.local.json" in text_lower:
        return "claude", 0.8
    if ".codex/" in text_lower or "config.toml" in text_lower or "agents.md" in text_lower:
        return "codex", 0.8
    if ".kiro/" in text_lower or "aws-ipl" in text_lower or "langgraph" in text_lower:
        return "kiro", 0.8
    if "anysphere" in text_lower or ".cursor" in text_lower:
        return "cursor", 0.8

    # P3: Unique phrases
    if "cheerleading" in text_lower or "fluff" in text_lower:
        return "codex", 0.7
    if "requirements-first" in text_lower or "design-first workflow" in text_lower:
        return "kiro", 0.7
    if "startline:endline:filepath" in text_lower:
        return "cursor", 0.7
    if "compaction retry" in text_lower or "bypasspermissions" in text_lower:
        return "claude", 0.7

    # P4: Fallback - use ML features
    return "uncertain", 0.0


# ============================================================
# TRAINING SCRIPT
# ============================================================

def load_dataset(filepath: str) -> tuple:
    """Load JSONL dataset."""
    X, y = [], []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line.strip())
            X.append(entry['text'])
            y.append(entry['label'])
    return X, y


def train_sklearn(X_train, y_train):
    """Train a scikit-learn classifier."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier

    # Convert to feature vectors
    feature_dicts = [extract_features(x) for x in X_train]
    feature_keys = sorted(feature_dicts[0].keys())
    X_features = np.array([[d[k] for k in feature_keys] for d in feature_dicts])

    # Also add TF-IDF on raw text for robustness
    vectorizer = TfidfVectorizer(ngram_range=(1, 3), max_features=500, analyzer='char_wb')
    X_tfidf = vectorizer.fit_transform(X_train)

    # Build pipeline with both feature sets
    from sklearn.decomposition import TruncatedSVD

    # Combine features
    svd = TruncatedSVD(n_components=50)
    X_tfidf_reduced = svd.fit_transform(X_tfidf)

    X_combined = np.hstack([X_features, X_tfidf_reduced])

    clf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
    clf.fit(X_combined, y_train)

    return clf, vectorizer, svd, feature_keys


def predict(clf, vectorizer, svd, feature_keys, text: str) -> tuple:
    """Predict tool label for a single text."""
    # Try rule-based first
    label, confidence = rule_based_classify(text)
    if confidence >= 0.95:
        return label, confidence

    # Fall back to ML
    feats = extract_features(text)
    X_feat = np.array([[feats[k] for k in feature_keys]])
    X_tfidf = vectorizer.transform([text])
    X_tfidf_red = svd.transform(X_tfidf)
    X_combined = np.hstack([X_feat, X_tfidf_red])

    proba = clf.predict_proba(X_combined)[0]
    idx = np.argmax(proba)
    return clf.classes_[idx], proba[idx]


def evaluate(clf, vectorizer, svd, feature_keys, X_test, y_test):
    """Evaluate classifier accuracy."""
    from sklearn.metrics import classification_report, confusion_matrix

    y_pred = []
    y_conf = []
    for x in X_test:
        label, conf = predict(clf, vectorizer, svd, feature_keys, x)
        y_pred.append(label)
        y_conf.append(conf)

    print("\n" + "=" * 60)
    print("CLASSIFICATION REPORT")
    print("=" * 60)
    print(classification_report(y_test, y_pred))

    print("=" * 60)
    print("CONFUSION MATRIX")
    print("=" * 60)
    cm = confusion_matrix(y_test, y_pred, labels=["cursor", "codex", "claude", "kiro"])
    print("              cursor  codex  claude  kiro")
    for i, label in enumerate(["cursor", "codex", "claude", "kiro"]):
        print(f"{label:>12}  " + "  ".join(f"{cm[i][j]:>5}" for j in range(4)))

    # Accuracy
    correct = sum(1 for p, t in zip(y_pred, y_test, strict=False) if p == t)
    print(f"\nAccuracy: {correct}/{len(y_test)} = {correct/len(y_test):.2%}")

    # Low-confidence cases
    low_conf = [(x, p, t, c) for x, p, t, c in zip(X_test, y_pred, y_test, y_conf, strict=False) if c < 0.8]
    if low_conf:
        print(f"\nLow confidence predictions (<0.8): {len(low_conf)}")
        for x, p, t, c in low_conf[:5]:
            print(f"  True={t} Pred={p} Conf={c:.2f} Text={x[:100]}...")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="AI Coding Tool Router Classifier")
    parser.add_argument("--train", action="store_true", help="Train the model")
    parser.add_argument("--predict", type=str, help="Predict a single prompt")
    parser.add_argument("--test", action="store_true", help="Run on test set")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark accuracy")
    parser.add_argument("--model-path", type=str, default="C:/Users/zhugu/Desktop/router_model.pkl",
                        help="Path to save/load model")
    args = parser.parse_args()

    # Load combined dataset
    dataset_path = "C:/Users/zhugu/Desktop/combined_training_data.jsonl"
    if not os.path.exists(dataset_path):
        print(f"Dataset not found: {dataset_path}")
        print("Using built-in training samples...")
        # Fall back to built-in samples
        X_train, y_train = [], []
        for label, texts in [
            ("cursor", ["You are gpt-4o. You are running as a coding agent in the Cursor IDE"]),
            ("codex", ["You are Codex, a coding agent based on GPT-5"]),
            ("claude", ["You are Claude Code, Anthropic's official CLI for Claude"]),
            ("kiro", ["You are a helpful assistant that can execute tasks using createExecuteBashTool"]),
        ]:
            X_train.append(texts[0])
            y_train.append(label)
    else:
        X_train, y_train = load_dataset(dataset_path)
        print(f"Loaded {len(X_train)} training samples")

    if args.train or args.benchmark or args.test:
        print("Training classifier...")
        clf, vectorizer, svd, feature_keys = train_sklearn(X_train, y_train)
        print(f"Trained on {len(X_train)} samples")

        # Save model
        import pickle
        with open(args.model_path, 'wb') as f:
            pickle.dump({
                'clf': clf,
                'vectorizer': vectorizer,
                'svd': svd,
                'feature_keys': feature_keys,
            }, f)
        print(f"Model saved to {args.model_path}")

        if args.benchmark or args.test:
            # Load adversarial test set
            adv_path = "C:/Users/zhugu/Desktop/adversarial_test_set.jsonl"
            if os.path.exists(adv_path):
                X_test, y_test = load_dataset(adv_path)
                print(f"Loaded {len(X_test)} adversarial test samples")
                evaluate(clf, vectorizer, svd, feature_keys, X_test, y_test)

    if args.predict:
        # Load model
        import pickle
        with open(args.model_path, 'rb') as f:
            model = pickle.load(f)
        label, conf = predict(model['clf'], model['vectorizer'], model['svd'],
                              model['feature_keys'], args.predict)
        print(f"Prediction: {label} (confidence: {conf:.2%})")


if __name__ == "__main__":
    main()
