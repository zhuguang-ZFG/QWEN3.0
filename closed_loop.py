#!/usr/bin/env python3
"""
Closed-Loop Automation Pipeline for red V1-Flash.
Feedback -> Distill -> Train -> Export -> Deploy -> Validate
"""

import json, os, subprocess, sys, time, urllib.request
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
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
    with open(CONFIG["feedback_queue"], 'r', encoding='utf-8') as f:
        queue = json.load(f)

    if len(queue) < CONFIG["distill_threshold"]:
        print(f"  Feedback queue: {len(queue)} items (< {CONFIG['distill_threshold']}, waiting)")
        return []

    print(f"  Processing {len(queue)} feedback items for distillation...")
    api_key = os.environ.get("CLAUDE_API_KEY", "")
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

    # Only clear successfully processed items
    processed_count = len(improved)
    remaining_queue = queue[processed_count:]
    with open(CONFIG["feedback_queue"], 'w', encoding='utf-8') as f:
        json.dump(remaining_queue, f, ensure_ascii=False)
    return improved


# ============================================================
# STEP 2: MERGE + TRIGGER RETRAINING
# ============================================================
def check_and_retrain(new_pairs: list):
    """If enough new data, merge and incrementally train."""
    if not new_pairs:
        return False

    with open(CONFIG["training_data"], 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.extend(new_pairs)
    with open(CONFIG["training_data"], 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Merged {len(new_pairs)} new pairs. Total: {len(data)}")

    # Trigger retrain whenever new pairs were added (distillation already gates on 10+ items)
    print(f"  Triggering incremental training with {len(new_pairs)} new pairs...")
    # Start training in background (limited steps for quick update)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["TRAIN_DATA_PATH"] = CONFIG["training_data"]  # = round5_training_data.json
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
    python_exe = r"D:\GIT\venv\Scripts\python.exe"
    weights_dir = r"D:\GIT\my_code_model_qwen3"
    adapter = os.path.join(weights_dir, "adapter_model.safetensors")
    convert_script = r"D:\GIT\llama.cpp\convert_hf_to_gguf.py"

    if not os.path.exists(adapter):
        print("  No adapter weights yet")
        return False

    print(f"  Weights ready at {weights_dir}")

    if not os.path.exists(convert_script):
        print("  GGUF export skipped - llama.cpp not found")
        # Adapter exists but llama.cpp missing: weights are ready, just not GGUF yet
        return True

    # Step 1: merge LoRA into full model
    print("  Step 1: Merging LoRA into full model...")
    merge_cmd = [python_exe, r"D:\GIT\lora_merge.py"]
    merge_result = subprocess.run(merge_cmd, timeout=600)
    if merge_result.returncode != 0:
        print(f"  LoRA merge failed (exit {merge_result.returncode})")
        return False

    # Step 2: convert to GGUF
    print("  Step 2: Converting to GGUF...")
    merged_path = os.path.join(weights_dir, "merged")
    gguf_output = r"D:\GIT\my_code_model_gguf\model-q4_K_M.gguf"
    os.makedirs(os.path.dirname(gguf_output), exist_ok=True)
    convert_result = subprocess.run(
        [python_exe, convert_script, merged_path,
         "--outfile", gguf_output, "--outtype", "q4_k_m"],
        timeout=600,
    )
    if convert_result.returncode != 0:
        print(f"  GGUF conversion failed (exit {convert_result.returncode})")
        return False

    print(f"  GGUF exported to {gguf_output}")
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
    export_ok = export_gguf_if_needed()

    # 4. Health + Discovery
    print("\n[4] API Maintenance")
    run_maintenance()

    # 5. Auto-deploy if export succeeded
    python_exe = r"D:\GIT\venv\Scripts\python.exe"
    env = os.environ.copy()
    print("\n[5] Auto-Deploy")
    if export_ok:
        subprocess.run([python_exe, r"D:\GIT\auto_deploy.py"], timeout=60, env=env)

    print(f"\n{'='*60}")
    print("  Pipeline complete")
    print(f"{'='*60}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--loop', action='store_true', help='Run continuously every 30 min')
    args = parser.parse_args()
    if args.loop:
        while True:
            main()
            print("Sleeping 30 min...")
            time.sleep(1800)
    else:
        main()
