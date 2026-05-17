#!/usr/bin/env python3
"""
Master Orchestrator: GRPO + Multi-LoRA + Adversarial Evolution.
The 弯道超车 pipeline for red V1-Flash.
"""

import json, os, subprocess, sys, time
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PIPELINE = [
    {
        "name": "SFT Fine-Tuning",
        "script": "train_model.py",
        "trigger": "New data >= 500 pairs",
        "status": "Round 4 running",
    },
    {
        "name": "GRPO Self-Evolution",
        "script": "grpo_train.py",
        "trigger": "After SFT completes",
        "status": "Ready",
    },
    {
        "name": "Multi-LoRA Routing",
        "script": "multi_lora_router.py",
        "trigger": "Always active",
        "status": "Ready",
    },
    {
        "name": "Adversarial Evolution",
        "script": "adversarial_self_evolution.py",
        "trigger": "Daily at 22:00",
        "status": "Ready",
    },
    {
        "name": "DPO Preference Training",
        "script": "train_dpo.py",
        "trigger": "After 500+ evolved pairs",
        "status": "Ready",
    },
    {
        "name": "Closed-Loop Pipeline",
        "script": "closed_loop.py",
        "trigger": "Daily at 20:00",
        "status": "Active",
    },
    {
        "name": "API Health Check",
        "script": "api_health_checker.py",
        "trigger": "Daily at 08:00",
        "status": "Active",
    },
    {
        "name": "API Auto-Discovery",
        "script": "api_auto_discovery.py",
        "trigger": "Daily at 08:00",
        "status": "Active",
    },
]


def main():
    print("=" * 60)
    print(f"  red V1-Flash Master Orchestrator")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print(f"\n{'Pipeline':<25} {'Trigger':<25} {'Status'}")
    print("-" * 70)
    for step in PIPELINE:
        print(f"  {step['name']:<23} {step['trigger']:<25} {step['status']}")

    # Check Round 4 progress
    r4 = r"D:\GIT\my_code_model_qwen3"
    if os.path.exists(r4):
        ckpts = [d for d in os.listdir(r4) if d.startswith('checkpoint')]
        adapter = os.path.exists(os.path.join(r4, 'adapter_model.safetensors'))
        print(f"\n  Round 4: {len(ckpts)} checkpoints, adapter={'SAVED' if adapter else 'training...'}")

    # Check DPO data
    dpo = r"D:\GIT\dpo_preferences.json"
    if os.path.exists(dpo):
        d = json.load(open(dpo, 'r', encoding='utf-8'))
        print(f"  DPO data: {len(d)} pairs ready")

    # Check evolved data
    evo = r"D:\GIT\evolved_training_data.json"
    if os.path.exists(evo):
        e = json.load(open(evo, 'r', encoding='utf-8'))
        print(f"  Evolved data: {len(e)} pairs")


if __name__ == "__main__":
    main()
