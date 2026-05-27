# LiMa 防遗忘训练方案 — 数据混合策略

> 参考: LLaMA-Factory mix_strategy + DPO
> 框架: trl.SFTTrainer（不换框架，借鉴策略）
> 日期: 2026-05-18

---

## 核心原理

```
灾难性遗忘 = 新数据梯度覆盖旧权重
解决方案 = 每个 batch 都混入旧数据（Replay Buffer）

LLaMA-Factory 做法:
  mix_strategy: "interleave"  → 多数据集交错采样
  mix_ratio: [0.3, 0.7]      → 30% 旧数据 + 70% 新数据

我们的做法:
  在 prepare_training_data() 中实现相同逻辑
  输出单个 merged.jsonl → 喂给 trl.SFTTrainer
```

---

## 数据混合配置

```python
MIX_CONFIG = {
    "replay_ratio": 0.30,      # 30% 旧轮回放
    "new_knowledge_ratio": 0.35,  # 35% 新知识
    "anti_hallucination_ratio": 0.20,  # 20% 防幻觉
    "identity_ratio": 0.15,    # 15% 身份强化
}

REPLAY_SOURCES = [
    ("round8_merged.json", 500),
    ("round10_merged.json", 500),
    ("round12_merged.json", 500),
    ("round13_merged.json", 500),
    ("round14_codex_context.json", 200),
    ("round14_context_construction.json", 200),
]

ANCHOR_SAMPLES = 160  # 每轮必含的锚定样本（不参与随机采样）
```

---

## 实现方案

### 文件: `prepare_r15_data.py`

功能:
1. 从旧轮数据随机采样 30%（replay buffer）
2. 加载新知识数据 35%
3. 加载防幻觉负样本 20%
4. 加载身份强化数据 15%
5. 插入锚定样本（固定不变）
6. 全部打乱顺序
7. 输出 round15_train.jsonl

### 训练参数调整

```python
# R15 vs R14 对比
R14_CONFIG = {
    "learning_rate": 2e-5,
    "warmup_ratio": 0.05,
    "num_train_epochs": 3,
}

R15_CONFIG = {
    "learning_rate": 1.5e-5,   # 降低 25%，减少旧知识覆盖
    "warmup_ratio": 0.10,      # 更长 warmup，平滑过渡
    "num_train_epochs": 2,     # 减少 epoch，防止过拟合
    "weight_decay": 0.01,      # 轻微正则化
}
```

---

## 验证方案

训练完成后运行评估脚本，检查:
- 旧知识保留率（从 R8 测试集抽 50 题）
- 身份正确率（"你是谁" × 20 次）
- 幻觉率（故意问不存在的 API × 20 次）
- 新知识掌握率（Cursor 架构 × 10 题）
