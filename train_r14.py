"""
Round 14 LoRA Fine-tuning for Qwen3-1.7B Routing Model
Training data: 1864 synthetic routing examples
Method: LoRA via SFTTrainer (trl)
"""
import os, json, time, torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model, TaskType
from trl import SFTTrainer, SFTConfig

# === Paths ===
BASE_MODEL = "D:/GIT/my_code_model_qwen3_r13/final"
TRAIN_DATA = "D:/GIT/data/training_data/routing_r14_synthetic.json"
OUTPUT_DIR = "D:/GIT/my_code_model_qwen3_r14"
FINAL_DIR = "D:/GIT/my_code_model_qwen3_r14/final"

# === Load training data ===
print("=" * 60)
print("Round 14 LoRA Training - Qwen3-1.7B Routing Model")
print("=" * 60)
print(f"\nLoading training data from: {TRAIN_DATA}")
with open(TRAIN_DATA, "r", encoding="utf-8") as f:
    raw_data = json.load(f)
print(f"  Total examples: {len(raw_data)}")

# === Load tokenizer and model ===
print(f"\nLoading base model from: {BASE_MODEL}")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)
model.config.use_cache = False
print(f"  Model loaded. Parameters: {model.num_parameters():,}")

# === LoRA Configuration ===
print("\nConfiguring LoRA (r=16, alpha=32, dropout=0.05)...")
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    bias="none",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# === Prepare dataset ===
print("\nPreparing dataset with chat template...")

def format_chat(example):
    messages = example["messages"]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    return {"text": text}

dataset = Dataset.from_list(raw_data)
dataset = dataset.map(format_chat, remove_columns=["messages"])
print(f"  Dataset ready: {len(dataset)} examples")

# Show a sample
sample = dataset[0]["text"]
print(f"\n  Sample (first 200 chars):\n  {sample[:200]}...")

# === Training Configuration ===
print("\nSetting up training...")
os.makedirs(OUTPUT_DIR, exist_ok=True)

training_args = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    warmup_ratio=0.05,
    lr_scheduler_type="cosine",
    logging_steps=10,
    save_strategy="epoch",
    save_total_limit=3,
    bf16=True,
    max_length=256,
    dataset_text_field="text",
    optim="adamw_torch",
    report_to="none",
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
)

# === Train ===
trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
)

print(f"\n{'=' * 60}")
print("Starting training...")
print(f"  Epochs: 3")
print(f"  Batch size: 4 x 4 grad_accum = effective 16")
print(f"  Learning rate: 2e-4")
print(f"  Max seq length: 256")
print(f"{'=' * 60}\n")

start_time = time.time()
train_result = trainer.train()
elapsed = time.time() - start_time

# === Print stats ===
print(f"\n{'=' * 60}")
print("Training Complete!")
print(f"{'=' * 60}")
print(f"  Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
print(f"  Final loss: {train_result.training_loss:.4f}")
print(f"  Total steps: {train_result.global_step}")
# === Merge LoRA into base model ===
print(f"\nMerging LoRA adapter into base model...")
merged_model = model.merge_and_unload()

print(f"Saving merged model to: {FINAL_DIR}")
os.makedirs(FINAL_DIR, exist_ok=True)
merged_model.save_pretrained(FINAL_DIR, safe_serialization=True)
tokenizer.save_pretrained(FINAL_DIR)

print(f"\n{'=' * 60}")
print("Round 14 training complete!")
print(f"  Merged model saved to: {FINAL_DIR}")
print(f"  Training loss: {train_result.training_loss:.4f}")
print(f"  Total time: {elapsed/60:.1f} minutes")
print(f"{'=' * 60}")
