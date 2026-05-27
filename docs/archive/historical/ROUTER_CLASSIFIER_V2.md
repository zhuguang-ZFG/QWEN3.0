# 路由分类器 V2 集成方案

> 来源: router_classifier_v2.py + routing_classifier_prompt_v2.txt
> 目标: 将信号字典加权评分机制集成到 smart_router.py
> 日期: 2026-05-18

---

## 一、当前问题

`smart_router.py` 的 `rule_classify()` 使用纯正则匹配：
- 无权重区分（所有匹配等价）
- 无置信度输出（要么匹配要么不匹配）
- 无法区分"强信号"和"弱信号"
- 新增工具/后端需要手写正则

---

## 二、V2 方案：信号字典 + 加权评分

### 2.1 核心架构

```
用户请求
  ↓
前缀提取（前 800 字符）
  ↓
信号字典匹配（6 维度 × N 关键词）
  ↓
加权评分（身份 3.0 > 工具 2.0 > 格式 1.5 > 配置 1.0）
  ↓
置信度阈值判断
  ├─ ≥0.90 → 直接路由
  ├─ 0.75-0.90 → 路由 + 标记低置信度
  └─ <0.75 → fallback 到本地模型分类
```

### 2.2 信号字典设计

```python
SIGNAL_DICT = {
    "code_generation": {
        "identity": ["写代码", "实现", "开发", "编写函数", "create"],
        "tools": ["python", "javascript", "react", "vue", "api"],
        "complexity": ["算法", "架构", "设计模式", "重构"],
    },
    "debugging": {
        "identity": ["报错", "bug", "修复", "error", "fix"],
        "tools": ["traceback", "stack trace", "exception"],
        "context": ["为什么", "不工作", "失败"],
    },
    "explanation": {
        "identity": ["解释", "什么是", "怎么理解", "原理"],
        "context": ["区别", "对比", "为什么要"],
    },
    "hardware": {
        "identity": ["esp32", "stm32", "arduino", "grbl", "gpio"],
        "tools": ["串口", "i2c", "spi", "pwm", "adc"],
        "config": ["$", "参数", "配置", "固件"],
    },
    "trivial": {
        "identity": ["你好", "hello", "hi", "谢谢", "再见"],
    },
}
```

### 2.3 权重配置

```python
SIGNAL_WEIGHTS = {
    "identity": 3.0,    # 最强信号：直接表明意图
    "tools": 2.0,       # 次强：提到具体技术栈
    "complexity": 1.5,  # 中等：复杂度指标
    "context": 1.5,     # 中等：上下文线索
    "config": 1.0,      # 弱信号：配置相关
}
```

### 2.4 置信度计算

```python
def compute_confidence(total_score):
    if total_score >= 8.0:
        return 0.95
    elif total_score >= 5.0:
        return 0.90
    elif total_score >= 3.0:
        return 0.75
    elif total_score >= 1.5:
        return 0.60
    return 0.40
```

---

## 三、与现有代码的集成点

### 3.1 替换 `rule_classify()`

```python
# 当前: rule_classify() → 纯正则，返回 intent 字符串
# 改为: signal_classify() → 加权评分，返回 (intent, confidence, evidence)
```

### 3.2 在 `analyze()` 中的位置

```
analyze() 流程:
  1. model_route() → 本地模型分类（如果可用）
  2. signal_classify() → 信号字典加权评分 ← 新增
  3. rule_classify() → 纯正则兜底（保留）
  4. model_classify() → LM Studio 分类（最后手段）
```

### 3.3 置信度驱动路由

```python
intent, confidence, evidence = signal_classify(query)
if confidence >= 0.90:
    return intent  # 高置信度，直接用
elif confidence >= 0.75:
    return intent  # 中置信度，用但标记
else:
    # 低置信度，继续尝试下一层分类
    pass
```

---

## 四、实施步骤

```
Step 1: 在 smart_router.py 中添加 SIGNAL_DICT 和 SIGNAL_WEIGHTS
Step 2: 实现 signal_classify(query) 函数
Step 3: 修改 analyze() 流程，插入 signal_classify
Step 4: 添加置信度到 route() 结果中
Step 5: 测试验证（10 个典型查询）
```

---

## 五、验收标准

- [ ] signal_classify 对 "写一个快排" 返回 (code_generation, ≥0.90)
- [ ] signal_classify 对 "报错 TypeError" 返回 (debugging, ≥0.90)
- [ ] signal_classify 对 "你好" 返回 (trivial, ≥0.90)
- [ ] signal_classify 对 "ESP32 GPIO 配置" 返回 (hardware, ≥0.90)
- [ ] 低置信度查询正确 fallback 到模型分类
- [ ] 不影响现有路由的正确性
