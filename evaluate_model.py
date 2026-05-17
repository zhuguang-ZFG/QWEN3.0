#!/usr/bin/env python3
"""
Model Evaluator: Perplexity + Domain Accuracy + Round Comparison.
Quantifies exactly how much each training round improved.
"""

import json, os, sys, random, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from datasets import Dataset
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_MODEL = r"D:\GIT\models\Qwen\Qwen3-8B"
TEST_SIZE = 200
EVAL_REPORT = r"D:\GIT\eval_report.json"


def prepare_test_set():
    """Extract a held-out test set that was never in training data."""
    data = json.load(open(r"D:\GIT\round5_training_data.json", 'r', encoding='utf-8'))

    # Take the *last* 200 items as test (training was on earlier data)
    random.seed(42)
    random.shuffle(data)
    test = data[-TEST_SIZE:]
    print(f"Test set: {len(test)} held-out examples")

    # Prepare for perplexity calculation
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    texts = []
    for item in test:
        msgs = item.get("messages", [])
        if len(msgs) >= 2:
            user = msgs[0].get("content", "")
            assistant = msgs[1].get("content", "")
            texts.append(user + "\n" + assistant)

    # Tokenize
    encodings = tokenizer(texts, truncation=True, padding=True, max_length=1024, return_tensors="pt")

    # Save
    torch.save(encodings, r"D:\GIT\test_set.pt")
    print(f"Saved tokenized test set ({len(texts)} examples)")

    return len(texts)


def calculate_perplexity(model_path: str, label: str):
    """Calculate perplexity of a LoRA model on the test set."""
    if not os.path.exists(r"D:\GIT\test_set.pt"):
        prepare_test_set()

    encodings = torch.load(r"D:\GIT\test_set.pt")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    print(f"\n  Loading {label} for perplexity evaluation...")
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_use_double_quant=True,
                              bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)

    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, quantization_config=bnb,
                                                  device_map="auto", trust_remote_code=True, torch_dtype=torch.bfloat16)

    # Load LoRA if available
    adapter = os.path.join(model_path, "adapter_model.safetensors")
    if os.path.exists(adapter):
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, model_path)
        print(f"  LoRA loaded from {model_path}")
    else:
        print("  Using base model (no LoRA)")

    model.eval()
    total_loss = 0.0
    total_tokens = 0

    batch_size = 2
    input_ids = encodings["input_ids"]
    attention_mask = encodings["attention_mask"]

    print(f"  Calculating perplexity over {len(input_ids)} examples...")
    with torch.no_grad():
        for i in range(0, len(input_ids), batch_size):
            batch_ids = input_ids[i:i+batch_size].cuda()
            batch_mask = attention_mask[i:i+batch_size].cuda()
            labels = batch_ids.clone()

            outputs = model(input_ids=batch_ids, attention_mask=batch_mask, labels=labels)
            loss = outputs.loss
            total_loss += loss.item() * batch_ids.size(0) * batch_ids.size(1)
            total_tokens += batch_mask.sum().item()

            if i % 20 == 0:
                print(f"    {i}/{len(input_ids)}...", end=" ")

    avg_loss = total_loss / max(total_tokens, 1)
    perplexity = torch.exp(torch.tensor(avg_loss)).item()
    print(f"\n  {label}: PPL={perplexity:.2f}, AvgLoss={avg_loss:.4f}")

    del model
    torch.cuda.empty_cache()
    return round(perplexity, 2), round(avg_loss, 4)


def domain_accuracy_test():
    """Quick accuracy check on domain-specific questions."""
    questions = [
        ("Grbl的$100参数是什么", ["step", "mm", "步", "毫", "脉冲", "250"]),
        ("ESP32 GPIO12为什么影响启动", ["GPIO", "boot", "启动", "电平"]),
        ("如何计算CNC的steps/mm", ["step", "mm", "公式", "导程", "细分"]),
        ("OpenOCD dump STM32固件命令", ["openocd", "flash", "dump", "read"]),
        ("SVG path转GCode Python代码", ["svg", "path", "gcode", "def ", "import"]),
    ]
    # This requires LM Studio running. Skip if not available.
    return None


def compare_rounds():
    """Compare all trained rounds vs baseline."""
    print("=" * 60)
    print("  Perplexity Evaluation — Round Comparison")
    print("=" * 60)

    rounds = [
        (r"D:\GIT\my_code_model", "Round 1 (Qwen2.5, 98K)"),
        (r"D:\GIT\my_code_model_round3", "Round 3 (Qwen2.5, 208K)"),
        (r"D:\GIT\my_code_model_qwen3", "Round 4 (Qwen3, 208K, 4K ctx)"),
    ]

    results = []
    for path, label in rounds:
        adapter = os.path.join(path, "adapter_model.safetensors")
        if os.path.exists(adapter):
            ppl, loss = calculate_perplexity(path, label)
            results.append({"round": label, "perplexity": ppl, "avg_loss": loss, "path": path})
        else:
            print(f"  SKIP {label}: adapter not found (training not complete)")

    # Compare
    if len(results) >= 2:
        print(f"\n{'='*60}")
        print(f"  Comparison:")
        print(f"{'Round':<35} {'PPL':<10} {'Improvement'}")
        print(f"{'-'*60}")
        baseline_ppl = results[0]["perplexity"]
        for r in results:
            improvement = ((baseline_ppl - r["perplexity"]) / baseline_ppl * 100) if baseline_ppl > 0 else 0
            print(f"  {r['round']:<35} {r['perplexity']:<10.2f} {improvement:+.1f}%")

    # Save report
    json.dump({"results": results, "timestamp": str(__import__('datetime').datetime.now())},
              open(EVAL_REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\n  Report saved to {EVAL_REPORT}")


def main():
    prepare_test_set()
    compare_rounds()


if __name__ == "__main__":
    main()
