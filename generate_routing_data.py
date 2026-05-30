"""generate_routing_data.py — 从路由日志自动生成路由训练数据。
读取 distill_queue/pending/ 中带评分的日志，生成路由模型训练样本。
"""
import json, os, glob

PENDING_DIR = "D:/GIT/data/distill_queue/pending/"
OUTPUT_PATH = "D:/GIT/data/training_data/round8_routing_feedback.json"
SYSTEM_PROMPT = "你是AI路由编排器。分析用户请求，输出JSON路由决策。不要回答问题本身。"

# 后端能力描述（用于生成 reason）
BACKEND_REASONS = {
    'longcat_thinking': '需要推理能力的问题',
    'longcat': '综合性强的复杂问题',
    'longcat_lite': '简单快速回答',
    'longcat_chat': '通用对话',
    'nvidia_qwen_coder': '代码生成/修改任务',
    'nvidia_nemotron': '嵌入式/数值计算',
    'nvidia_llama70b': '通用问题',
    'nvidia_llama4': '快速通用',
    'or_deepseek_r1': '复杂推理',
    'or_qwen3_235b': '代码+中文',
    'or_llama70b': '通用备选',
    'deepseek_pro': '最强推理（付费）',
    'claude': '最强综合（付费）',
    'local': 'GRBL/GCode简单查表',
    'chinamobile': '通用兜底',
}


def load_logs() -> list:
    """读取所有带评分的路由日志。"""
    logs = []
    for f in glob.glob(os.path.join(PENDING_DIR, "*.json")):
        try:
            with open(f, encoding='utf-8') as fp:
                entry = json.load(fp)
                if 'quality_score' in entry:
                    logs.append(entry)
        except Exception as exc:
            _log.debug("generate_routing_data.py: {}", type(exc).__name__)
    return logs


def generate_training_data(logs: list) -> list:
    """从日志生成路由训练样本。"""
    samples = []
    for log in logs:
        score = log.get('quality_score', 0)
        backend = log.get('source_backend', 'unknown')
        intent = log.get('intent', 'unknown')
        query = log.get('query', '')
        complexity = log.get('complexity', 0.5)

        if not query or backend == 'unknown':
            continue

        # 高分 = 路由正确，直接作为正样本
        if score >= 0.8:
            reason = BACKEND_REASONS.get(backend, '最佳匹配')
            routing_decision = {
                "intent": intent,
                "complexity": complexity,
                "needs_orchestration": False,
                "backend": backend,
                "reason": reason
            }
            samples.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": json.dumps(routing_decision, ensure_ascii=False)}
                ],
                "source": "routing_feedback_positive",
                "quality_score": score
            })

    return samples


def run(min_logs: int = 50) -> dict:
    """主函数：加载日志，生成训练数据，写入文件。"""
    logs = load_logs()
    if len(logs) < min_logs:
        print(f"[routing_data] 日志不足 {min_logs} 条（当前 {len(logs)}），跳过")
        return {"generated": 0, "total_logs": len(logs)}

    samples = generate_training_data(logs)

    # 确保输出目录存在
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # 追加到现有文件
    existing = []
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding='utf-8') as f:
            existing = json.load(f)

    existing.extend(samples)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"[routing_data] 生成 {len(samples)} 条路由训练样本，总计 {len(existing)} 条")
    return {"generated": len(samples), "total": len(existing)}


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    result = run(min_logs=1)  # 测试时降低阈值
    print(result)
