#!/usr/bin/env python3
"""
auto_retrain.py — 自动训练迭代闭环

当 fallback 日志满 100 条时，自动：
1. 读取日志
2. 自动标注正确路由（用 fallback_backend 作为正确答案）
3. 生成训练数据
4. 追加到训练集
5. 重新训练模型
6. 验证新模型准确率 > 旧模型
7. 热更新模型

触发条件：fallback_log.jsonl 达到 THRESHOLD 条记录
运行方式：python auto_retrain.py（手动）或 cron/定时任务
"""

import os
import json
import time
import sys
import subprocess

# ── 配置 ──────────────────────────────────────────────────────────────────────
FALLBACK_LOG = "D:/GIT/data/fallback_log.jsonl"
TRAINING_DIR = "D:/GIT/data/training_data/"
MODEL_PATH = "D:/GIT/my_code_model_qwen3_r12/final"
NEW_MODEL_PATH = "D:/GIT/my_code_model_qwen3_auto/final"
EVAL_DIR = "D:/GIT/data/eval/"
THRESHOLD = 100  # 日志满100条触发训练
MIN_ACCURACY_IMPROVEMENT = 0.02  # 新模型至少提升2%准确率才替换

# 训练超参数
TRAIN_EPOCHS = 3
TRAIN_BATCH_SIZE = 4
TRAIN_LR = 2e-5
LORA_R = 16
LORA_ALPHA = 32
MAX_SEQ_LEN = 512


def read_fallback_log() -> list[dict]:
    """读取 fallback 日志文件，返回条目列表。"""
    if not os.path.exists(FALLBACK_LOG):
        return []
    entries = []
    with open(FALLBACK_LOG, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def generate_training_data(entries: list[dict]) -> list[dict]:
    """从 fallback 日志生成训练数据。
    fallback_backend 是实际成功的后端，作为正确答案。
    """
    training_data = []
    for entry in entries:
        query = entry.get("query", "")
        fallback_backend = entry.get("fallback_backend", "")
        ide = entry.get("ide", "unknown")
        intent = entry.get("intent", "general")

        if not query or not fallback_backend:
            continue

        # 构造路由决策 JSON 作为 assistant 输出
        decision = {
            "action": "route",
            "backend": fallback_backend,
            "needs_tools": False,
            "ide_detected": ide,
            "intent": intent.replace("fallback_same_tier_", "").replace("fallback_upgrade_", ""),
            "complexity": 0.5,
        }

        training_data.append({
            "messages": [
                {
                    "role": "system",
                    "content": "你是red V1flash智能路由决策器。分析用户请求，输出路由决策JSON。"
                },
                {
                    "role": "user",
                    "content": f"IDE上下文: {ide}\n用户问题: {query}"
                },
                {
                    "role": "assistant",
                    "content": json.dumps(decision, ensure_ascii=False)
                }
            ],
            "source": "auto_retrain_fallback"
        })

    return training_data


def save_training_data(training_data: list[dict]) -> str:
    """保存训练数据到文件，返回文件路径。"""
    os.makedirs(TRAINING_DIR, exist_ok=True)
    timestamp = int(time.time())
    filename = f"auto_retrain_{timestamp}.json"
    filepath = os.path.join(TRAINING_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(training_data, f, ensure_ascii=False, indent=2)
    return filepath


def merge_all_training_data() -> str:
    """合并所有训练数据文件为一个统一训练集。"""
    all_data = []
    if not os.path.exists(TRAINING_DIR):
        return ""

    for fname in os.listdir(TRAINING_DIR):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(TRAINING_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                all_data.extend(data)
        except (json.JSONDecodeError, IOError):
            continue

    merged_path = os.path.join(TRAINING_DIR, "merged_all.json")
    with open(merged_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    return merged_path


def run_training(merged_data_path: str) -> bool:
    """执行模型训练。返回 True 表示训练成功。"""
    os.makedirs(os.path.dirname(NEW_MODEL_PATH), exist_ok=True)

    # 构建训练命令（使用 transformers + peft LoRA）
    train_script = os.path.join(os.path.dirname(__file__), "train_router.py")

    if not os.path.exists(train_script):
        print(f"[AUTO_RETRAIN] 训练脚本不存在: {train_script}")
        print("[AUTO_RETRAIN] 尝试使用 transformers CLI 训练...")
        # Fallback: 直接用 python 调用训练
        cmd = [
            sys.executable, "-m", "transformers.trainer",
            "--model_name_or_path", MODEL_PATH,
            "--train_file", merged_data_path,
            "--output_dir", NEW_MODEL_PATH,
            "--num_train_epochs", str(TRAIN_EPOCHS),
            "--per_device_train_batch_size", str(TRAIN_BATCH_SIZE),
            "--learning_rate", str(TRAIN_LR),
            "--save_strategy", "no",
            "--logging_steps", "10",
        ]
    else:
        cmd = [
            sys.executable, train_script,
            "--base_model", MODEL_PATH,
            "--data_path", merged_data_path,
            "--output_dir", NEW_MODEL_PATH,
            "--epochs", str(TRAIN_EPOCHS),
            "--batch_size", str(TRAIN_BATCH_SIZE),
            "--lr", str(TRAIN_LR),
            "--lora_r", str(LORA_R),
            "--lora_alpha", str(LORA_ALPHA),
            "--max_seq_len", str(MAX_SEQ_LEN),
        ]

    print(f"[AUTO_RETRAIN] 训练命令: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode == 0:
            print("[AUTO_RETRAIN] 训练完成")
            return True
        else:
            print(f"[AUTO_RETRAIN] 训练失败: {result.stderr[:500]}")
            return False
    except subprocess.TimeoutExpired:
        print("[AUTO_RETRAIN] 训练超时 (>2h)")
        return False
    except Exception as e:
        print(f"[AUTO_RETRAIN] 训练异常: {e}")
        return False


def evaluate_model(model_path: str, test_data: list[dict]) -> float:
    """评估模型准确率。返回 0.0-1.0 的准确率。"""
    if not os.path.exists(model_path):
        print(f"[AUTO_RETRAIN] 模型路径不存在: {model_path}")
        return 0.0

    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        import re

        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, trust_remote_code=True,
            torch_dtype="auto", device_map="auto")
        model.eval()

        correct = 0
        total = 0

        for sample in test_data[:50]:  # 最多评估50条，避免太慢
            messages = sample.get("messages", [])
            if len(messages) < 3:
                continue

            expected_output = messages[2]["content"]
            try:
                expected_json = json.loads(expected_output)
                expected_backend = expected_json.get("backend", "")
            except json.JSONDecodeError:
                continue

            eval_messages = messages[:2]  # system + user
            text = tokenizer.apply_chat_template(
                eval_messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(text, return_tensors="pt").to(model.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs, max_new_tokens=200, do_sample=False)

            response = tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True)

            # 解析模型输出
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    pred = json.loads(json_match.group())
                    if pred.get("backend") == expected_backend:
                        correct += 1
                except json.JSONDecodeError:
                    pass

            total += 1

        accuracy = correct / total if total > 0 else 0.0
        print(f"[AUTO_RETRAIN] 模型评估: {correct}/{total} = {accuracy:.2%}")
        return accuracy

    except Exception as e:
        print(f"[AUTO_RETRAIN] 评估异常: {e}")
        return 0.0


def hot_reload_model(new_model_path: str) -> bool:
    """热更新模型：更新 smart_router.py 中的模型路径引用。
    通过修改 smart_router 模块的全局变量实现运行时切换。
    """
    try:
        # 方式1：直接修改 smart_router 模块变量（如果在同一进程）
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import smart_router
        smart_router.LOCAL_ROUTER_MODEL = new_model_path
        smart_router._local_model = None
        smart_router._local_tokenizer = None
        smart_router._local_model_failed = False
        print(f"[AUTO_RETRAIN] 热更新完成: {new_model_path}")
        return True
    except Exception as e:
        print(f"[AUTO_RETRAIN] 热更新失败: {e}")
        return False


def archive_log():
    """归档已处理的 fallback 日志。"""
    if os.path.exists(FALLBACK_LOG):
        backup_name = f"{FALLBACK_LOG}.{int(time.time())}.bak"
        os.rename(FALLBACK_LOG, backup_name)
        print(f"[AUTO_RETRAIN] 日志已归档: {backup_name}")


def check_and_retrain() -> bool:
    """主入口：检查日志量，满足条件时触发完整训练闭环。
    返回 True 表示成功完成训练并更新模型。
    """
    print("=" * 60)
    print("[AUTO_RETRAIN] 自动训练迭代闭环 - 检查中...")
    print(f"  模型路径: {MODEL_PATH}")
    print(f"  日志路径: {FALLBACK_LOG}")
    print(f"  触发阈值: {THRESHOLD} 条")
    print("=" * 60)

    # Step 1: 检查日志量
    entries = read_fallback_log()
    if len(entries) < THRESHOLD:
        print(f"[AUTO_RETRAIN] 日志量不足: {len(entries)}/{THRESHOLD}，跳过。")
        return False

    print(f"[AUTO_RETRAIN] 发现 {len(entries)} 条 fallback 记录，开始训练...")

    # Step 2: 生成训练数据
    training_data = generate_training_data(entries)
    if not training_data:
        print("[AUTO_RETRAIN] 无法生成有效训练数据，跳过。")
        return False
    print(f"[AUTO_RETRAIN] 生成 {len(training_data)} 条训练样本")

    # Step 3: 保存训练数据
    data_file = save_training_data(training_data)
    print(f"[AUTO_RETRAIN] 训练数据已保存: {data_file}")

    # Step 4: 合并所有训练数据
    merged_path = merge_all_training_data()
    if not merged_path:
        print("[AUTO_RETRAIN] 合并训练数据失败，跳过。")
        return False
    total_samples = len(json.load(open(merged_path, encoding='utf-8')))
    print(f"[AUTO_RETRAIN] 合并后总样本数: {total_samples}")

    # Step 5: 评估旧模型基线
    test_data = training_data[:20]  # 用新数据的前20条做测试
    old_accuracy = evaluate_model(MODEL_PATH, test_data)
    print(f"[AUTO_RETRAIN] 旧模型基线准确率: {old_accuracy:.2%}")

    # Step 6: 训练新模型
    success = run_training(merged_path)
    if not success:
        print("[AUTO_RETRAIN] 训练失败，保留旧模型。")
        return False

    # Step 7: 验证新模型
    if not os.path.exists(NEW_MODEL_PATH):
        print(f"[AUTO_RETRAIN] 新模型路径不存在: {NEW_MODEL_PATH}")
        return False

    new_accuracy = evaluate_model(NEW_MODEL_PATH, test_data)
    print(f"[AUTO_RETRAIN] 新模型准确率: {new_accuracy:.2%}")
    print(f"[AUTO_RETRAIN] 提升: {new_accuracy - old_accuracy:+.2%}")

    # Step 8: 判断是否替换
    if new_accuracy < old_accuracy + MIN_ACCURACY_IMPROVEMENT:
        print(f"[AUTO_RETRAIN] 新模型提升不足 ({MIN_ACCURACY_IMPROVEMENT:.0%})，保留旧模型。")
        return False

    # Step 9: 热更新模型
    hot_reload_model(NEW_MODEL_PATH)

    # Step 10: 归档日志
    archive_log()

    print("=" * 60)
    print("[AUTO_RETRAIN] 训练闭环完成！")
    print(f"  新模型: {NEW_MODEL_PATH}")
    print(f"  准确率: {old_accuracy:.2%} -> {new_accuracy:.2%}")
    print("=" * 60)
    return True


# ── CLI 入口 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="自动训练迭代闭环 - fallback 日志驱动的模型自动优化")
    parser.add_argument("--check", action="store_true",
                        help="检查日志量并在满足条件时触发训练")
    parser.add_argument("--force", action="store_true",
                        help="强制训练（忽略阈值）")
    parser.add_argument("--status", action="store_true",
                        help="显示当前状态（日志量、模型路径等）")
    parser.add_argument("--threshold", type=int, default=THRESHOLD,
                        help=f"触发训练的日志条数阈值（默认 {THRESHOLD}）")
    args = parser.parse_args()

    if args.threshold != THRESHOLD:
        THRESHOLD = args.threshold

    if args.status:
        entries = read_fallback_log()
        print(f"Fallback 日志: {len(entries)} 条")
        print(f"触发阈值: {THRESHOLD} 条")
        print(f"当前模型: {MODEL_PATH}")
        print(f"新模型输出: {NEW_MODEL_PATH}")
        print(f"训练数据目录: {TRAINING_DIR}")
        if entries:
            print(f"最新记录: {entries[-1].get('timestamp', 'N/A')}")
            # 统计 fallback 后端分布
            backends = {}
            for e in entries:
                fb = e.get("fallback_backend", "unknown")
                backends[fb] = backends.get(fb, 0) + 1
            print("Fallback 后端分布:")
            for b, count in sorted(backends.items(), key=lambda x: -x[1]):
                print(f"  {b}: {count}")
        sys.exit(0)

    if args.force:
        THRESHOLD = 1  # 强制模式：1条就触发

    if args.check or args.force:
        success = check_and_retrain()
        sys.exit(0 if success else 1)

    # 默认行为：检查并训练
    success = check_and_retrain()
    sys.exit(0 if success else 1)
