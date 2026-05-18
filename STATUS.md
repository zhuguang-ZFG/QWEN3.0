# LiMa AI 项目状态

> 更新时间: 2026-05-19 00:50
> 训练轮次: R14 完成 | R15 准备中

---

## 当前进度

### 模型训练
| 轮次 | 状态 | Loss | Accuracy | 备注 |
|------|------|------|----------|------|
| R13 | ✅ 完成 | 0.42 | 90.1% | 公司身份 + ESP32 |
| R14 | 🔄 训练中 | 0.47 | 89.6% | 上下文构造 + 工具架构 |
| R15 | 📋 数据准备完成 | - | - | 防遗忘 + 防幻觉 + ML路由 |

### 平台部署
| 服务 | 域名 | 状态 |
|------|------|------|
| 品牌官网 | www.donglicao.com | ✅ 运行中 |
| API 控制台 | api.donglicao.com | ✅ one-api → new-api 切换中 |
| 免费聊天 | chat.donglicao.com | ✅ NextChat 已上线 (HTTPS) |
| new-api | port 3003 | ✅ 容器运行中，等R14完成后切换 |

### 智能路由 (smart_router.py)
| 功能 | 状态 |
|------|------|
| 三层意图分类 (模型→信号→正则) | ✅ |
| Signal Classify V2 (加权评分) | ✅ 10/10 通过 |
| ML 路由分类器 (RandomForest, 24维特征) | ✅ 已集成 |
| Expand 模板按需加载 | ✅ 5 个模板 |
| IDE 元数据增强路由 | ✅ |
| 质量不达标 fallback 重试 | ✅ |
| 不确定性升级 [ERR] 防护 | ✅ |
| 截断续写用正确后端 | ✅ |

---

## 路由系统架构

```
用户请求
  ↓
Layer 0: Qwen3 R12 本地模型路由 (主路径)
  ↓ (不可用时)
Layer 1: 正则规则 (0ms)
  ↓ (未匹配)
Layer 1.1: Signal V2 加权评分 (0ms, 24维信号字典)
  ↓ (低置信度)
Layer 1.5: 本地 Qwen3 旧路径 (50-100ms)
  ↓ (不可用时)
Layer 2: LM Studio 模型分类
  ↓
ML Router: RandomForest 辅助决策 (context_feature_extractor)
  ↓
后端选择 → fallback 链 → expand 扩写 → API 调用
  ↓
质量检查 → 不确定性升级 → 截断续写 → 蒸馏日志
```

---

## 文件结构

### 核心代码
- `smart_router.py`: 智能路由引擎
- `server.py`: FastAPI 服务端
- `context_feature_extractor.py`: 24维特征提取器
- `train_router_model.py`: ML路由模型训练
- `generate_training_data.py`: 训练数据生成
- `prepare_r15_data.py`: R15 数据混合脚本

### 文档 (docs/)
- `PLATFORM_UPGRADE.md`: 平台升级设计
- `CONTEXT_ENGINEERING.md`: 上下文工程优化
- `ANTI_FORGETTING_STRATEGY.md`: 防遗忘训练策略
- `ROUND15_TRAINING_STRATEGY.md`: R15 训练配比
- `ROUTER_CLASSIFIER_V2.md`: 信号字典分类器
- `ai-coding-tools-context-patterns.md`: 7大工具对比
- `copilot-chat-context-construction.md`: Copilot 架构

### 训练数据 (data/training_data/)
- `routing_training_data_v3.jsonl`: 48条路由分类 V3
- `round15_cursor_auto_mode.json`: Cursor 架构知识
- `round15_anti_hallucination.json`: 防幻觉负样本
- `round15_identity.json`: 身份强化
- `round15_router_classification.jsonl`: 路由分类
- `feature_names.txt`: 39个特征名

### 模型 (data/models/)
- `router_ml_model.pkl`: RandomForest 路由模型

### 模板 (templates/)
- `expand_code.txt`: 代码生成扩写
- `expand_debug.txt`: 调试扩写
- `expand_explain.txt`: 解释扩写
- `expand_hardware.txt`: 硬件扩写
- `expand_default.txt`: 默认扩写
