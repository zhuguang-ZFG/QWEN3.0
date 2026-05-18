# LiMa AI 项目状态

> 更新时间: 2026-05-18 22:40
> 训练轮次: R14 进行中 (58%)

---

## 当前进度

### 模型训练
| 轮次 | 状态 | Loss | Accuracy | 备注 |
|------|------|------|----------|------|
| R13 | ✅ 完成 | 0.42 | 90.1% | 公司身份 + ESP32 |
| R14 | 🔄 训练中 | 0.47 | 89.6% | 上下文构造 + 工具架构 |
| R15 | 📋 数据准备完成 | - | - | 防遗忘 + 防幻觉 |

### 平台部署
| 服务 | 域名 | 状态 |
|------|------|------|
| 品牌官网 | www.donglicao.com | ✅ 运行中 |
| API 控制台 | api.donglicao.com | ✅ one-api 运行中 |
| 免费聊天 | chat.donglicao.com | ✅ NextChat 已上线 |
| new-api 升级 | api.donglicao.com | ⏳ 部署中 |

### 智能路由 (smart_router.py)
| 功能 | 状态 |
|------|------|
| 三层意图分类 (模型→信号→正则) | ✅ |
| Signal Classify V2 (加权评分) | ✅ 10/10 通过 |
| Expand 模板按需加载 | ✅ 5 个模板 |
| IDE 元数据增强路由 | ✅ |
| 质量不达标 fallback 重试 | ✅ |
| 不确定性升级 [ERR] 防护 | ✅ |
| 截断续写用正确后端 | ✅ |

---

## 本轮完成的工作

### 代码改动
- `smart_router.py`: 路由闭环修复 + Signal V2 + 模板加载 + IDE 路由
- `templates/expand_*.txt`: 5 个领域专用扩写模板
- `prepare_r15_data.py`: LLaMA-Factory 风格数据混合脚本

### 文档
- `docs/CONTEXT_ENGINEERING.md`: 上下文工程优化方案
- `docs/ANTI_FORGETTING_STRATEGY.md`: 防遗忘训练策略
- `docs/ROUND15_TRAINING_STRATEGY.md`: R15 训练数据配比
- `docs/ROUTER_CLASSIFIER_V2.md`: 信号字典分类器设计
- `docs/PLATFORM_UPGRADE.md`: 平台升级设计文档

### 训练数据 (Round 15 准备)
- `round15_cursor_auto_mode.json`: 4 条 Cursor 架构知识
- `round15_anti_hallucination.json`: 8 条防幻觉负样本
- `round15_identity.json`: 6 条身份强化
- `round15_router_classification.jsonl`: 27 条路由分类
- `round14_ai_tools_context.json`: 9 条工具对比

### 服务器运维
- NextChat 部署 (chat.donglicao.com, HTTPS)
- 旧站点清理 (释放 ~1GB)
- frpc 开机自启
- one-api 品牌定制 + GitHub 隐藏
