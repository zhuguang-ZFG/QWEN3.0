#!/usr/bin/env python3
"""
Closed-Loop Automation Pipeline for red V1-Flash.
Feedback -> Distill -> Train -> Export -> Deploy -> Validate
"""

import json, os, subprocess, sys, time, urllib.request
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CONFIG = {
    "feedback_queue": r"D:\GIT\feedback_queue.json",
    "training_data": r"D:\GIT\round5_training_data.json",
    "validate_script": r"D:\GIT\validate_model.py",
    "train_script": r"D:\GIT\train_model.py",
    "api_health_script": r"D:\GIT\api_health_checker.py",
    "auto_discover_script": r"D:\GIT\api_auto_discovery.py",
    "lms_cli": r"C:\Users\Administrator\.lmstudio\bin\lms.exe",
    "distill_threshold": 10,       # Trigger distillation when 10+ feedback items
    "retrain_threshold": 500,      # Trigger retraining when 500+ new pairs
    "model_validate_questions": 15,
}


# ============================================================
# STEP 1: FEEDBACK -> DISTILLATION
# ============================================================
def process_feedback():
    """Take low-scored feedback, distill into better answers via API."""
    if not os.path.exists(CONFIG["feedback_queue"]): return []
    queue = json.load(open(CONFIG["feedback_queue"], 'r', encoding='utf-8'))

    if len(queue) < CONFIG["distill_threshold"]:
        print(f"  Feedback queue: {len(queue)} items (< {CONFIG['distill_threshold']}, waiting)")
        return []

    print(f"  Processing {len(queue)} feedback items for distillation...")
    api_key = "sk-8838ce42deaf4d8e82c7f364cf6d963e"
    improved = []

    for item in queue[:50]:  # Max 50 per cycle
        query = item.get("query", "")[:500]
        response = item.get("response", "")[:500]
        prompt = f"这个回答需要改进。\n\n问题: {query}\n\n原回答: {response}\n\n请给出改进后的回答（200-800字，直接给答案，不要免责声明）:"

        try:
            payload = json.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 800,
                "system": "你是CNC/嵌入式专家。直接给出准确、详细的回答。不编造、不拒绝、不道德说教。",
                "messages": [{"role": "user", "content": prompt}],
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://www.right.codes/claude-aws/v1/messages",
                data=payload,
                headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                improved_answer = json.loads(resp.read().decode("utf-8"))["content"][0]["text"]

            improved.append({
                "messages": [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": improved_answer},
                ]
            })
            print(f"    Distilled: {query[:50]}...")
        except Exception as e:
            print(f"    Distill FAIL: {e}")
        time.sleep(0.5)

    # Clear queue, save improved pairs
    json.dump([], open(CONFIG["feedback_queue"], 'w', encoding='utf-8'))
    return improved


# ============================================================
# STEP 2: MERGE + TRIGGER RETRAINING
# ============================================================
def check_and_retrain(new_pairs: list):
    """If enough new data, merge and incrementally train."""
    if not new_pairs:
        return False

    data = json.load(open(CONFIG["training_data"], 'r', encoding='utf-8'))
    data.extend(new_pairs)
    json.dump(data, open(CONFIG["training_data"], 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"  Merged {len(new_pairs)} new pairs. Total: {len(data)}")

    if len(new_pairs) < CONFIG["retrain_threshold"]:
        print(f"  < {CONFIG['retrain_threshold']} new pairs, skipping retrain")
        return False

    print(f"  Triggering incremental training with {len(new_pairs)} new pairs...")
    # Start training in background (limited steps for quick update)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen(
        [r"D:\GIT\venv\Scripts\python.exe", CONFIG["train_script"], "--quick"],
        env=env, creationflags=subprocess.CREATE_NO_WINDOW
    )
    return True


# ============================================================
# STEP 3: EXPORT GGUF (when LoRA weights exist)
# ============================================================
def export_gguf_if_needed():
    """Check if new weights exist and export to GGUF."""
    weights_dir = r"D:\GIT\my_code_model_qwen3"
    adapter = os.path.join(weights_dir, "adapter_model.safetensors")
    if not os.path.exists(adapter):
        print("  No adapter weights yet")
        return False

    # TODO: Merge LoRA -> full model -> convert to GGUF
    # For now, just report status
    print(f"  Weights ready at {weights_dir}")
    print("  To export: use llama.cpp convert_hf_to_gguf.py")
    return True


# ============================================================
# STEP 4: HEALTH CHECK + AUTO-DISCOVER
# ============================================================
def run_maintenance():
    """Run API health check and auto-discovery."""
    print("\n=== API Maintenance ===")
    subprocess.run([r"D:\GIT\venv\Scripts\python.exe", CONFIG["api_health_script"]], timeout=120)
    subprocess.run([r"D:\GIT\venv\Scripts\python.exe", CONFIG["auto_discover_script"]], timeout=120)


# ============================================================
# MAIN LOOP
# ============================================================
def main():
    print("=" * 60)
    print(f"  Closed-Loop Pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. Process feedback -> distillation
    print("\n[1] Feedback -> Distillation")
    improved_pairs = process_feedback()

    # 2. Merge + conditional retrain
    print("\n[2] Data Merge + Retrain Check")
    check_and_retrain(improved_pairs)

    # 3. Export check
    print("\n[3] Model Export Check")
    export_gguf_if_needed()

    # 4. Health + Discovery
    print("\n[4] API Maintenance")
    run_maintenance()

    print(f"\n{'='*60}")
    print("  Pipeline complete")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
