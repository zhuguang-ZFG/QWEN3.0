#!/usr/bin/env python3
"""
DPO (Direct Preference Optimization) Training for red V1-Flash.
Uses ms-swift for one-command DPO with QLoRA.
"""

import json, os, random, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DPO_DATA = r"D:\GIT\dpo_preferences.json"
OUTPUT = r"D:\GIT\my_code_model_dpo"
BASE_MODEL = r"D:\GIT\models\Qwen\Qwen3-8B"
SFT_DATA = r"D:\GIT\round5_training_data.json"

# Generate DPO preference pairs
# chosen = our best distilled/curated answers
# rejected = boring generic answers (like what base Qwen would say)
def generate_dpo_data():
    print("Generating DPO preference pairs...")

    with open(SFT_DATA, 'r', encoding='utf-8') as f:
        sft = json.load(f)
    preferences = []
    rejected_templates = [
        "{question} 这个问题我不太确定，建议查阅官方文档获取准确信息。",
        "关于 {question}，这是一个很常见的问题。通常的做法是按照标准流程操作。具体细节因设备而异。",
        "作为AI助手，我建议你首先确认基础配置是否正确。{question} 需要根据实际环境调整，请参考用户手册。",
    ]

    for item in sft[:2000]:  # Use 2000 pairs for DPO (good balance)
        msgs = item.get("messages", [])
        if len(msgs) < 2: continue

        user_msg = msgs[0].get("content", "")
        chosen = msgs[1].get("content", "")

        if len(user_msg) < 10 or len(chosen) < 50: continue

        # Create a deliberately worse response
        template = random.choice(rejected_templates)
        topic = user_msg[:30].replace("\n", " ")
        rejected = template.replace("{question}", topic)

        preferences.append({
            "prompt": user_msg[:500],
            "chosen": chosen[:1000],
            "rejected": rejected[:500],
        })

    # Shuffle and save
    random.shuffle(preferences)
    with open(DPO_DATA, 'w', encoding='utf-8') as f:
        json.dump(preferences, f, ensure_ascii=False, indent=2)
    print(f"Generated {len(preferences)} DPO preference pairs")
    return len(preferences)


def train_dpo():
    """Run DPO training via ms-swift."""
    n = generate_dpo_data()

    cmd = [
        "swift", "rlhf",
        "--rlhf_type", "dpo",
        "--model", BASE_MODEL,
        "--train_type", "lora",
        "--dataset", DPO_DATA,
        "--lora_rank", "16",
        "--lora_alpha", "32",
        "--lora_target_modules", "ALL",
        "--num_train_epochs", "1",
        "--per_device_train_batch_size", "1",
        "--gradient_accumulation_steps", "8",
        "--learning_rate", "5e-6",
        "--beta", "0.1",
        "--max_length", "2048",
        "--output_dir", OUTPUT,
        "--save_steps", "200",
        "--logging_steps", "10",
        "--bf16", "true",
        "--dataset_num_proc", "2",
    ]

    print(f"\nStarting DPO training ({n} pairs)...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Training failed with exit code {result.returncode}")


def main():
    print("="*60)
    print("  DPO Training for red V1-Flash")
    print("="*60)
    train_dpo()


if __name__ == "__main__":
    main()
