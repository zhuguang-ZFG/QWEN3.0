
import os, json, torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

BASE_MODEL = 'D:/GIT/my_code_model_qwen3_r13/final'
OUTPUT_DIR = 'D:/GIT/my_code_model_qwen3_r14'

R13_DATA = 'D:/GIT/data/training_data/round13_train.jsonl'
ESP32_DATA = 'D:/GIT/data/training_data/round13_esp32_project.json'
COMPANY_DATA = 'D:/GIT/data/training_data/round13_company_identity.json'

# Merge all data
data = []
with open(R13_DATA, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            data.append(json.loads(line))

with open(ESP32_DATA, encoding='utf-8') as f:
    esp32 = json.loads(f.read())
    data.extend(esp32)

with open(COMPANY_DATA, encoding='utf-8') as f:
    company = json.loads(f.read())
    data.extend(company)

print(f'Total training samples: {len(data)} (R13: base, +ESP32: {len(esp32)}, +Company: {len(company)})')

# Save merged data
merged_path = 'D:/GIT/data/training_data/round14_train.jsonl'
with open(merged_path, 'w', encoding='utf-8') as f:
    for item in data:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')
print(f'Merged data saved to {merged_path}')

print(f'Loading base model from {BASE_MODEL}...')
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, trust_remote_code=True,
    torch_dtype=torch.bfloat16, device_map="auto"
)

def format_chat(example):
    messages = example.get('messages', [])
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    return {'text': text}

dataset = Dataset.from_list(data)
dataset = dataset.map(format_chat)

config = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-5,
    warmup_ratio=0.05,
    logging_steps=50,
    save_steps=500,
    save_total_limit=2,
    bf16=True,
    max_length=1024,
    dataset_text_field="text",
    report_to="none",
)

trainer = SFTTrainer(
    model=model, args=config,
    train_dataset=dataset, processing_class=tokenizer
)
trainer.train()
trainer.save_model(os.path.join(OUTPUT_DIR, 'final'))
tokenizer.save_pretrained(os.path.join(OUTPUT_DIR, 'final'))
print('Round 14 training complete!')
