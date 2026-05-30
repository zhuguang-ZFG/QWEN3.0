#!/usr/bin/env python3
"""
QLoRA fine-tuning script for Qwen2.5-7B-Instruct.
HuggingFace native - works on Windows with RTX 5060 Ti 16GB.

Usage:
  python train_model.py                     # Train
  python train_model.py --export_only       # Export to GGUF
  python train_model.py --export_only --use_llama_cpp  # Export via llama.cpp
"""

import os
import json
import argparse
import torch
import train_lock

# ========== CONFIGURATION ==========
MODEL_NAME = "Qwen/Qwen3-8B"
LOCAL_MODEL_PATH = r"D:\GIT\models\Qwen\Qwen3-8B"
OUTPUT_DIR = os.environ.get("TRAIN_OUTPUT_DIR", r"D:\GIT\my_code_model_qwen3")
DATA_PATH = os.environ.get("TRAIN_DATA_PATH", r"D:\GIT\round5_training_data.json")
RESUME_FROM = os.environ.get("TRAIN_RESUME_FROM", None) or None  # empty string → None
GGUF_OUTPUT = r"D:\GIT\my_code_model_gguf"

# Training hyperparameters - tuned for 16GB VRAM
MAX_SEQ_LENGTH = 4096  # Qwen3-8B supports 40K context, 4096 fits in 16GB
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0
BATCH_SIZE = 1  # Must be 1 for 16GB VRAM
GRADIENT_ACCUMULATION = 8  # Effective batch size = 8
LEARNING_RATE = float(os.environ.get("TRAIN_LEARNING_RATE", "2e-4"))
MAX_STEPS = int(os.environ.get("TRAIN_MAX_STEPS", "4000"))  # Round 6: 155K data, targeting ~0.3 epoch
WARMUP_RATIO = 0.05

# LoRA target modules
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]


def load_data(data_path):
    """Load training data."""
    from datasets import Dataset

    print(f"Loading data from {data_path}...")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"  Loaded {len(data)} conversations")
    return Dataset.from_list(data)


def format_messages(messages, tokenizer):
    """Format messages using Qwen chat template."""
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )


def train():
    """Main training function."""
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer

    # BitsAndBytes 4-bit quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    print(f"\nLoading model: {MODEL_NAME}")
    print("  This may take a few minutes to download...")

    # Use local model path if available, otherwise download from HF
    model_path = LOCAL_MODEL_PATH if os.path.isdir(LOCAL_MODEL_PATH) else MODEL_NAME
    if model_path == LOCAL_MODEL_PATH:
        print(f"  Using local model from: {model_path}")
    else:
        print(f"  Downloading from HuggingFace: {MODEL_NAME}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        padding_side="right",
        local_files_only=(model_path == LOCAL_MODEL_PATH),
    )
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        local_files_only=(model_path == LOCAL_MODEL_PATH),
    )

    # Prepare model for QLoRA
    model = prepare_model_for_kbit_training(model)

    # LoRA config
    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Resume from round 1 weights if available
    if RESUME_FROM and os.path.exists(os.path.join(RESUME_FROM, "adapter_model.safetensors")):
        print(f"\nLoading previous weights from: {RESUME_FROM}")
        from peft import PeftModel
        base_model = model.get_base_model()
        model = PeftModel.from_pretrained(base_model, RESUME_FROM, is_trainable=True)
        model.print_trainable_parameters()

    # Load data
    dataset = load_data(DATA_PATH)

    # Format dataset with chat template
    def format_dataset(example):
        messages = example["messages"]
        text = format_messages(messages, tokenizer)
        return {"text": text}

    formatted_dataset = dataset.map(format_dataset, batched=False)

    # Trainer config
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        warmup_steps=int(WARMUP_RATIO * MAX_STEPS),
        max_steps=MAX_STEPS,
        learning_rate=LEARNING_RATE,
        bf16=True,
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
        save_steps=100,
        save_total_limit=3,
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=formatted_dataset,
        args=training_args,
    )

    # Train!
    print("\n" + "=" * 60)
    print("Starting training...")
    print(f"  Model: {MODEL_NAME}")
    print(f"  LoRA rank: {LORA_R}")
    print(f"  Effective batch size: {BATCH_SIZE} x {GRADIENT_ACCUMULATION} = {BATCH_SIZE * GRADIENT_ACCUMULATION}")
    print(f"  Max steps: {MAX_STEPS}")
    print(f"  Learning rate: {LEARNING_RATE}")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60 + "\n")

    trainer_stats = trainer.train()

    # Save
    print("\nSaving model...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"Model saved to {OUTPUT_DIR}")

    print(f"\nTraining complete!")
    print(f"  Steps: {trainer_stats.global_step}")
    print(f"  Loss: {trainer_stats.training_loss:.4f}")


def export_gguf():
    """Export to GGUF format for Ollama."""
    print("\nExporting to GGUF...")

    # Method 1: Try llama.cpp conversion
    gguf_dir = GGUF_OUTPUT
    os.makedirs(gguf_dir, exist_ok=True)

    # Download and use llama.cpp converter
    print("Downloading llama.cpp for GGUF conversion...")

    import subprocess

    # Install llama-cpp-python for conversion
    try:
        subprocess.check_call([
            "D:/GIT/venv/Scripts/pip", "install",
            "llama-cpp-python",
            "--extra-index-url",
            "https://abetlen.github.io/llama-cpp-python/whl/cu128",
        ])
    except subprocess.CalledProcessError:
        # Fallback to CPU conversion
        print("  GPU build failed, using CPU conversion...")
        subprocess.check_call([
            "D:/GIT/venv/Scripts/pip", "install", "llama-cpp-python",
        ])

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    # Load base model + LoRA
    print("Loading model with LoRA weights...")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME, trust_remote_code=True
    )
    tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="cpu",
        trust_remote_code=True,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )

    # Merge LoRA
    model = PeftModel.from_pretrained(base_model, OUTPUT_DIR)
    model = model.merge_and_unload()

    # Save merged model
    merged_path = os.path.join(OUTPUT_DIR, "merged")
    model.save_pretrained(merged_path)
    tokenizer.save_pretrained(merged_path)
    print(f"Merged model saved to {merged_path}")

    # Convert to GGUF using llama-cpp-python
    print("Converting to GGUF (Q4_K_M quantization)...")

    # Use transformers->gguf conversion via llama.cpp
    gguf_path = os.path.join(gguf_dir, "model-q4_K_M.gguf")

    # Download llama.cpp convert script
    import urllib.request
    convert_script = os.path.join(gguf_dir, "convert_hf_to_gguf.py")
    if not os.path.exists(convert_script):
        url = "https://raw.githubusercontent.com/ggerganov/llama.cpp/master/convert_hf_to_gguf.py"
        urllib.request.urlretrieve(url, convert_script)

    # Run conversion
    subprocess.check_call([
        "D:/GIT/venv/Scripts/python", convert_script,
        merged_path,
        "--outfile", gguf_path,
        "--outtype", "q4_k_m",
    ])

    print(f"\nGGUF file: {gguf_path}")

    # Create Ollama Modelfile
    modelfile_path = os.path.join(gguf_dir, "Modelfile")
    with open(modelfile_path, 'w', encoding='utf-8') as f:
        f.write(f'''FROM "{gguf_path}"

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM 你是 red V1-Flash，由深圳市动力巢科技训练。专注于 CNC 嵌入式开发、SVG 图像处理、和 AI 工具链的编程助手。使用中文回答。对于不确定的内容，必须明确说明不确定，严禁编造信息。
''')

    print(f"\nTo deploy to Ollama:")
    print(f"  ollama create zhuguang-code-model -f \"{modelfile_path}\"")
    print(f"  ollama run zhuguang-code-model")


def main():
    parser = argparse.ArgumentParser(description='Train QLoRA model on Qwen2.5-7B')
    parser.add_argument('--export_only', action='store_true', help='Only export trained model to GGUF')
    parser.add_argument('--test', action='store_true', help='Quick test - load model and verify GPU')
    parser.add_argument('--quick', action='store_true', help='Quick incremental training: 100 steps only, no warmup')
    args = parser.parse_args()

    if args.quick:
        global MAX_STEPS, WARMUP_RATIO
        MAX_STEPS = 100
        WARMUP_RATIO = 0

    if args.test:
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        return

    if args.export_only:
        export_gguf()
        return

    # 检查并发训练锁
    if not train_lock.acquire("manual"):
        print("另一个训练进程正在运行，请等待其完成后再试。")
        print(f"锁信息：{train_lock.get_lock_info()}")
        return

    # Full training
    try:
        train()
        print("\nTraining done! To export to GGUF:")
        print("  python train_model.py --export_only")
    finally:
        train_lock.release()


if __name__ == '__main__':
    main()
