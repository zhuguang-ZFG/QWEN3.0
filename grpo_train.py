#!/usr/bin/env python3
"""
GRPO (Group Relative Policy Optimization) - DeepSeek-R1's secret sauce.
Model generates 4 answers → self-evaluates → keeps best → evolves.
Runs on 16GB with QLoRA.
"""

import json, os, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_MODEL = r"D:\GIT\models\Qwen\Qwen3-8B"
SFT_DATA = r"D:\GIT\round5_training_data.json"
GRPO_OUTPUT = r"D:\GIT\my_code_model_grpo"


def prepare_grpo_data():
    """GRPO needs only prompts, no labels. Model self-evaluates groups."""
    sft = json.load(open(SFT_DATA, 'r', encoding='utf-8'))
    prompts = []
    seen = set()
    for item in sft:
        msgs = item.get("messages", [])
        if len(msgs) < 1: continue
        prompt = msgs[0].get("content", "")[:400]
        key = prompt[:60]
        if key in seen or len(prompt) < 20: continue
        seen.add(key)
        prompts.append({"prompt": prompt})
        if len(prompts) >= 1000: break

    json.dump(prompts, open(r"D:\GIT\grpo_prompts.json", 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"GRPO prompts prepared: {len(prompts)}")
    return len(prompts)


def train_grpo():
    n = prepare_grpo_data()
    print(f"\nStarting GRPO training ({n} prompts, 4 answers each)...\n")

    cmd = [
        "swift", "rlhf",
        "--rlhf_type", "grpo",
        "--model", BASE_MODEL,
        "--train_type", "lora",
        "--dataset", r"D:\GIT\grpo_prompts.json",
        "--lora_rank", "8",
        "--lora_alpha", "16",
        "--num_train_epochs", "1",
        "--per_device_train_batch_size", "1",
        "--gradient_accumulation_steps", "16",
        "--learning_rate", "1e-5",
        "--num_generations", "4",
        "--max_completion_length", "512",
        "--beta", "0.04",
        "--output_dir", GRPO_OUTPUT,
        "--save_steps", "200",
        "--bf16",
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(cmd, env=env)


if __name__ == "__main__":
    train_grpo()
