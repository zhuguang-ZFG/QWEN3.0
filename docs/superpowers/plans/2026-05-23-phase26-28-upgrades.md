# Phase 26-28: 三大升级设计文档

> 来源: OpenClaw-RL, sub2api, Cognee
> 原则: 先文档后执行，最小改动最大收益

---

## Phase 26: GRPO 优势估计 (OpenClaw-RL)

**目标:** 替代线性 +0.05/-0.1 为 clipped advantage update

**当前问题:**
- 线性更新无法区分"比平均好多少"
- 所有成功等价（快速成功 vs 勉强成功）
- 所有失败等价（超时 vs 完全不可用）

**算法:**
```
baseline = avg_success_rate[scenario]  # 所有后端在该场景的平均成功率
reward = 1.0 if success else 0.0
advantage = reward - baseline
lr = 0.08
max_delta = 0.15
delta = clip(advantage * lr, -max_delta, +max_delta)
weight += delta
```

**效果:**
- 当所有后端都成功时，成功不再加分（advantage ≈ 0）
- 当大多数后端失败时，成功大幅加分（advantage ≈ 0.8）
- 防止权重爆炸（clipped）

**文件:** `context_pipeline/routing_weights.py` — 修改 record_success/record_failure

---

## Phase 27: 并发控制 + 智能轮转 (sub2api)

**目标:** 升级 key_pool 为并发感知 + 429 智能轮转

**当前问题:**
- key_pool 只做 SWRR 轮转，不感知并发
- 同一个 key 可能被 10 个请求同时使用 → 触发 rate limit
- 429 后没有自动轮转到下一个 key

**设计:**
```python
class ConcurrencyAwareKeyPool:
    max_concurrent_per_key: int = 3
    in_flight: dict[str, int]  # key → 当前并发数

    def acquire(key) → bool:
        if in_flight[key] >= max_concurrent:
            return False  # 需要轮转
        in_flight[key] += 1
        return True

    def release(key):
        in_flight[key] -= 1

    def rotate_on_429(current_key) → next_key:
        # 标记当前 key 冷却 60s
        # 返回下一个可用 key
```

**文件:** 新建 `context_pipeline/concurrency_pool.py`

---

## Phase 28: Feedback-Weight EMA 衰减 (Cognee)

**目标:** Skill Store 从 TTL 过期改为 feedback_weight EMA 衰减

**当前问题:**
- 技能 72h 后统一过期，不区分好坏
- 成功的技能和失败的技能同等对待
- 无法"越用越准"

**设计:**
```python
class RoutingSkill:
    weight: float = 1.0  # 新增
    alpha: float = 0.1

    def on_success():
        weight *= (1 + alpha * 0.5)  # 成功 → 权重增长
        weight = min(weight, 3.0)

    def on_failure():
        weight *= (1 - alpha)  # 失败 → 权重衰减

    @property
    def is_expired():
        return weight < 0.1  # 权重过低 → 淘汰
```

**效果:**
- 频繁成功的技能权重持续增长（最高 3.0）
- 偶尔失败的技能权重缓慢衰减
- 持续失败的技能自动淘汰（weight < 0.1）
- 不再依赖固定 TTL

**文件:** `context_pipeline/skill_store.py` — 修改 RoutingSkill + recall/crystallize

---

*设计完成，开始实施。*
