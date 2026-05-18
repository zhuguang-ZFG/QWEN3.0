# LiMa 上下文工程优化方案

> 来源: Cursor Auto Mode 逆向分析 + 7 大 AI 编程工具对比
> 目标: 将行业最佳实践转化为 LiMa 的差异化优势
> 日期: 2026-05-18

---

## 核心洞察

Cursor 强大的秘密不是 prompt 写得好，而是**上下文工程**——用最少的 token 传递最多的有效信息。LiMa 作为 API 路由层，可以在不同层面借鉴这些模式。

---

## 一、极简路由 Prompt（已有优势，可强化）

### Cursor 做法
System prompt 仅 642 tokens，把空间留给代码上下文。

### LiMa 适配
我们的路由模型 prompt 应该极短——只做分类决策，不做回答：

```
当前: expand() 用 ~200 tokens 的 system prompt 指导扩写
目标: 路由决策 prompt < 100 tokens，扩写 prompt < 150 tokens
```

**行动项：**
- [ ] 精简 `SYS` 变量，去掉冗余指令
- [ ] expand prompt 只保留核心：任务类型 + 输出格式要求
- [ ] 节省的 token 空间用于传递更多用户上下文

---

## 二、双层模型架构（已实现，需文档化）

### Cursor 做法
Core Model（推理规划）+ Apply Model（执行编辑），成本降低 10-50x。

### LiMa 已有的双层架构
```
┌─────────────────────────────────────┐
│  Layer 0: 路由模型 (Qwen3 4B, 本地) │
│  - 意图分类                          │
│  - 复杂度评估                        │
│  - 后端选择                          │
│  - 成本: ¥0（本地推理）              │
├─────────────────────────────────────┤
│  Layer 1: 执行模型 (云端后端)        │
│  - DeepSeek Pro/Flash               │
│  - Claude                           │
│  - LongCat                          │
│  - 成本: 按 token 计费              │
└─────────────────────────────────────┘
```

### 可强化方向
- 路由模型增加"预判复杂度"能力 → 简单问题直接本地回答，不调用云端
- Apply 层增加"格式化后处理" → 统一输出格式，减少后端差异感知

**行动项：**
- [ ] 路由模型训练加入 complexity 标签（trivial/medium/hard）
- [ ] trivial 类直接本地回答，省去 API 调用延迟和成本
- [ ] 增加 post-processor 统一输出格式

---

## 三、Lazy Loading — 按需加载（新增能力）

### Cursor 做法
- Skills 在上下文中只放名字（2 tokens/skill）
- 完整内容在 AI 决定需要时才加载
- 长工具输出写入文件，模型用 read/tail 按需访问

### LiMa 适配：expand 模板按需加载

当前 expand() 对所有请求用同一个 prompt。改为：

```python
# 当前：固定 expand prompt
expand_prompt = "你是提示词工程师，请扩写以下请求..."

# 优化：按 intent 加载专用模板
EXPAND_TEMPLATES = {
    'code_generation': 'templates/expand_code.txt',
    'debugging': 'templates/expand_debug.txt',
    'explanation': 'templates/expand_explain.txt',
    'hardware': 'templates/expand_hardware.txt',
}

def expand(query, intent):
    template_path = EXPAND_TEMPLATES.get(intent, 'templates/expand_default.txt')
    template = load_template(template_path)  # 按需加载
    return call_local(template + query)
```

**优势：**
- 每个领域的扩写模板可以独立优化
- 不浪费 token 在无关领域的指令上
- 新领域只需添加模板文件

**行动项：**
- [ ] 创建 `templates/expand_*.txt` 目录
- [ ] 按 intent 分类编写专用扩写模板
- [ ] expand() 改为按需加载模板

---

## 四、静默上下文增强（LiMa 独有优势）

### Cursor 做法
用户输入前自动注入：打开文件、git 状态、lint 错误、终端输出。

### LiMa 适配：IDE 元数据透传

当用户通过 Cursor/Continue/Claude Code 调用 LiMa API 时，
IDE 会在请求中携带元数据。我们可以利用这些信息增强路由决策：

```python
# 从请求 headers 或 metadata 中提取 IDE 上下文
def extract_ide_context(request):
    return {
        'ide': request.headers.get('X-IDE', 'unknown'),
        'file_ext': request.headers.get('X-File-Extension', ''),
        'project_lang': request.headers.get('X-Project-Language', ''),
        'cursor_position': request.headers.get('X-Cursor-Position', ''),
    }

# 利用 IDE 上下文优化路由
def enhanced_route(query, ide_context):
    if ide_context['file_ext'] == '.rs':
        # Rust 文件 → 优先用擅长 Rust 的后端
        prefer = 'claude'
    elif ide_context['file_ext'] in ('.ino', '.cpp') and 'esp32' in query.lower():
        # 嵌入式开发 → 用长上下文模型
        prefer = 'longcat'
    return route(query, prefer=prefer)
```

**LiMa 独有优势：**
- 我们是中间层，能看到所有 IDE 的请求元数据
- 可以根据文件类型、项目语言自动优化路由
- 用户无感知，但回答质量更高

**行动项：**
- [ ] server.py 解析 IDE 元数据 headers
- [ ] smart_router.py 的 route() 接受 ide_context 参数
- [ ] 根据文件扩展名/项目语言调整后端偏好

---

## 五、可恢复压缩（多轮对话优化）

### Cursor 做法
压缩后原文存为文件，模型可以 read() 回溯。

### LiMa 适配：对话摘要 + 完整历史缓存

对于多轮对话场景（通过 one-api 的 conversation 功能）：

```python
# 多轮对话管理
class ConversationManager:
    def compress(self, messages):
        if len(messages) > 10:
            # 前 N-3 条压缩为摘要
            summary = self.summarize(messages[:-3])
            # 原文存入 Redis/文件，可回溯
            self.store_full_history(messages)
            return [
                {'role': 'system', 'content': f'[对话摘要] {summary}'},
                *messages[-3:]  # 保留最近 3 条
            ]
        return messages
```

**行动项：**
- [ ] 实现 ConversationManager 类
- [ ] 多轮对话超过 10 条时自动压缩
- [ ] 压缩摘要用本地模型生成（零成本）

---

## 六、成本感知路由（LiMa 核心差异化）

### Cursor 做法
Core Model 用最强模型，Apply Model 用廉价模型，成本降 10-50x。

### LiMa 的成本优化矩阵

```
┌─────────────────────────────────────────────────────────┐
│  用户请求                                                │
│    ↓                                                    │
│  路由模型判断复杂度                                      │
│    ├─ trivial → 本地模型直答（¥0）                      │
│    ├─ simple → Nvidia 免费模型（¥0）                    │
│    ├─ medium → DeepSeek Flash（¥0.001/次）              │
│    ├─ hard → DeepSeek Pro（¥0.01/次）                   │
│    └─ expert → Claude Opus（¥0.05/次）                  │
│                                                         │
│  成本节省: 80% 请求走免费/低成本路径                     │
└─────────────────────────────────────────────────────────┘
```

**这是 LiMa 相对于直接调用 Claude/GPT 的核心价值：**
- 用户付 ¥29/月
- 80% 请求走免费后端（¥0）
- 15% 请求走低成本后端（¥0.001）
- 5% 请求走高端后端（¥0.05）
- 平均成本 ¥0.003/次 vs 直接调用 ¥0.03/次 → **10x 成本优势**

**行动项：**
- [ ] 路由模型训练加入 cost_tier 标签
- [ ] 实现动态成本预算（用户月度额度内自动分配）
- [ ] 仪表盘展示成本节省比例

---

## 七、实施优先级

| 优先级 | 优化项 | 预期收益 | 工作量 |
|--------|--------|----------|--------|
| P0 | 成本感知路由 | 10x 成本优势 | 中（训练数据+模型） |
| P0 | IDE 元数据透传 | 路由准确率 +15% | 低（解析 headers） |
| P1 | Expand 模板按需加载 | 扩写质量 +20% | 低（模板文件） |
| P1 | 极简路由 prompt | 推理速度 +10% | 低（精简文本） |
| P2 | 可恢复压缩 | 多轮对话体验 | 中（新模块） |
| P2 | 复杂度预判 | 减少 API 调用 | 中（训练数据） |

---

## 八、与竞品的差异化定位

```
Cursor:  IDE 深度集成 → 上下文自动获取 → 编码体验最佳
Claude Code: 强模型 + 丰富工具 → 复杂任务能力最强
Aider:   结构化代码理解 → Repo Map → 大仓库导航

LiMa:    智能路由 + 成本优化 → 一个 Key 调用 N 个模型
         核心价值: 用户不需要知道哪个模型最适合当前任务
         我们帮用户做选择，同时把成本降到最低
```

**LiMa 不是要替代 Cursor/Claude Code，而是作为它们的后端：**
- Cursor 用户设置 LiMa 为 API → 自动路由到最优模型
- Claude Code 用户设置 LiMa 为 Provider → 成本降低 10x
- 独立开发者直接用 chat.donglicao.com → 免费体验
