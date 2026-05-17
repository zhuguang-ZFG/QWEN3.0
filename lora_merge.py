#!/usr/bin/env python3
"""
Multi-LoRA Merger: Combine domain LoRA + code LoRA + general LoRA into one.
Works on 16GB without extra VRAM.
"""

import torch, os, json, sys
from peft import PeftModel
from transformers import AutoModelForCausalLM
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r"D:\GIT\models\Qwen\Qwen3-8B"
MERGE_OUTPUT = r"D:\GIT\my_code_model_merged"
LORA_SOURCES = {
    "cnc_domain": r"D:\GIT\my_code_model_qwen3",      # Our trained LoRA (CNC/ESP32/RE)
    "code_style": r"D:\GIT\my_code_model_round3",     # Round 3 LoRA (code patterns from Claude Code etc)
    "general_knowledge": r"D:\GIT\my_code_model",     # Round 1 base LoRA
}

MERGE_WEIGHTS = {"cnc_domain": 0.5, "code_style": 0.3, "general_knowledge": 0.2}


def merge_loras():
    """Load base model, apply multiple LoRAs with weighted averaging, save merged."""
    print("Loading base model (4-bit)...")
    from transformers import BitsAndBytesConfig
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_use_double_quant=True,
                              bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)

    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                  device_map="auto", trust_remote_code=True, torch_dtype=torch.bfloat16)

    # Load available LoRA weights
    loaded_loras = {}
    for name, path in LORA_SOURCES.items():
        adapter = os.path.join(path, "adapter_model.safetensors")
        if os.path.exists(adapter):
            print(f"  Loading {name} from {path} ({os.path.getsize(adapter)/1024/1024:.1f}MB)")
            loaded_loras[name] = path
        else:
            print(f"  SKIP {name}: no adapter found (training not complete)")

    if not loaded_loras:
        print("No LoRA adapters available yet. Wait for Round 4 to complete.")
        return

    # Load first LoRA as base, then merge others
    first = list(loaded_loras.keys())[0]
    print(f"\nLoading primary LoRA: {first}")
    model = PeftModel.from_pretrained(model, loaded_loras[first])
    print(f"  Primary LoRA loaded")

    # Track merged state
    merged_sources = [first]
    total_weight = MERGE_WEIGHTS.get(first, 1.0)

    # Additional LoRAs get weight-averaged (simple mean of adapter weights)
    for name, path in loaded_loras.items():
        if name == first: continue
        print(f"  Merging {name} (weight={MERGE_WEIGHTS.get(name, 0.3)})...")

        # Load and merge
        temp_model = PeftModel.from_pretrained(model, path)
        temp_weight = MERGE_WEIGHTS.get(name, 0.3)

        # Weighted average: merge our LoRA with temp LoRA
        # Using linear interpolation: merged = w1 * lora1 + w2 * lora2 / (w1 + w2)
        for our_param, temp_param in zip(model.parameters(), temp_model.parameters()):
            if our_param.requires_grad:
                our_param.data = (our_param.data * total_weight + temp_param.data * temp_weight) / (total_weight + temp_weight)

        total_weight += temp_weight
        merged_sources.append(name)
        del temp_model

    print(f"\nMerged {len(merged_sources)} LoRAs: {merged_sources}")

    # Save merged adapter
    model.save_pretrained(MERGE_OUTPUT)
    print(f"Saved to {MERGE_OUTPUT}")

    # Save merge manifest
    json.dump({"base_model": BASE, "sources": loaded_loras, "weights": MERGE_WEIGHTS, "timestamp": str(__import__('datetime').datetime.now())},
              open(os.path.join(MERGE_OUTPUT, "merge_manifest.json"), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("  Multi-LoRA Merger")
    print("  Combine domain specialists into one model")
    print("=" * 60)
    merge_loras()


if __name__ == "__main__":
    main()
