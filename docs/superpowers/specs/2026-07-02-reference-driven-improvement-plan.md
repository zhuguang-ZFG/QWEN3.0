# 基于参考项目的改善计划

- **日期**：2026-07-02
- **状态**：待用户审批
- **前提**：系统瘦身已完成（P0/P1/P2 全部闭环），生产部署验证通过
- **原则**：先做减法已完成，现在做精准加法。每项改进必须解决 LiMa 当前真实痛点，不为参考而参考。
- **参考核实**：所有参考项目的 Stars 和活跃度已于 2026-07-02 通过 GitHub 实际访问核实（见 `progress.md` 同日条目）

---

## 一、差距分析：LiMa 现状 vs 参考项目

### 1.1 路由分类器 vs Semantic Router（3.7k 星）

**LiMa 现状**（`routing_classifier.py` + `routing_intent.py`）：
- 请求类型分类（ide/chat/vision/image）：纯规则匹配（User-Agent、IDE 指纹、图片块检测），**零 LLM 调用**，已很快
- 意图分析（`analyze_intent`）：正则规则 `_ANALYZE_RULES`（40+ 条）+ 信号词加权 `_signal_classify` + 可选 LLM 后备（`maybe_instructor_intent`）
- **痛点**：正则规则维护成本高，新意图需要手写规则；LLM 后备增加延迟（500ms-2s）

**Semantic Router 做得更好的**：
- 语义向量空间匹配，无需手写正则，新意图只需加几个示例句
- 毫秒级决策（向量余弦相似度，无需 LLM 生成）
- 混合路由层（HybridRouteLayer）= 关键词 + 语义双重匹配

**差距评估**：中等。LiMa 的正则规则覆盖面已很广，但新增设备场景（如语音控制）时正则维护成本上升。

### 1.2 路径优化 vs vpype（917 星）

**LiMa 现状**（`xiaozhi_drawing/`）：
- `path_optimizer.py`：Douglas-Peucker 简化 + 缩放居中
- `path_ordering.py`：贪心最近邻笔画排序（允许反向）
- `skeleton_tracer.py`：骨架像素→折线追踪
- `text_to_path.py`：fonttools 字形提取→SVG path
- **痛点**：路径优化是单体函数，无管道架构；无插件扩展点；缺少多层 SVG 支持

**vpype 做得更好的**：
- 管道架构（`read → layout → optimize → write`），每步可独立替换
- 插件系统，自定义优化器可注册为命令
- 多层 SVG 文件处理（layer/色/笔），支持多遍绘制图层管理
- 路径合并/拆分/裁剪等高级操作

**差距评估**：小。LiMa 的绘图路径处理已能工作（骨架化+排序+简化），vpype 的管道架构是更好的组织方式但当前规模下不是瓶颈。

### 1.3 后端注册 vs LiteLLM（52.3k 星）

**LiMa 现状**（`backends_registry/`）：
- 按提供商分文件（`groq.py`、`nvidia.py`、`openrouter.py` 等），每文件导出 `BACKENDS` dict
- `__init__.py` 逐个 `update()` 合并
- 每个后端是 dict（url/key/model/fmt/timeout/caps）
- **痛点**：无统一 adapter 接口；新后端需要手写 dict 条目；无自动发现/注册机制

**LiteLLM 做得更好的**：
- 每个 provider 一个 adapter 文件，实现统一接口
- `litellm.completion()` 自动路由到正确 adapter
- 内置 cost tracking、retry、fallback 策略链
- 虚拟 Key 管理 + 花费追踪

**差距评估**：小。LiMa 的 170+ 后端已稳定运行，dict 模式虽简单但有效。LiteLLM 的 adapter 模式更适合 1000+ 后端规模，当前不是瓶颈。

### 1.4 设备状态管理 vs eventsourcing（1.7k 星）

**LiMa 现状**：
- 设备状态用 SQLite 表（`devices`、`tasks`），直接 CRUD
- 无事件溯源，状态变更无审计链
- **痛点**：设备任务历史只能查最终状态，无法回放状态变迁

**eventsourcing 做得更好的**：
- 事件存储 + 投影，可回放任意时间点的设备状态
- Snapshot 优化长事件流
- CQRS 读写分离

**差距评估**：YAGNI。LiMa 的设备管理是个人/小团队场景，事件溯源的复杂度收益不覆盖成本。记入未来备选。

### 1.5 固件运动控制 vs FluidNC（2.5k 星）

**LiMa 现状**（U1 固件）：
- 基于 Grbl_Esp32（已停更），已关 WiFi 编译
- 运动规划、GCode 解析、步进控制继承自 Grbl 核心
- **痛点**：Grbl_Esp32 已停更（2023-02），无安全更新；配置方式硬编码（`machine_def.h`）

**FluidNC 做得更好的**：
- YAML 声明式机器配置（无需重新编译）
- 持续维护（2026-05 最后提交），安全更新活跃
- 更好的电机抽象层（支持多种驱动器）
- WebUI 内置（LiMa 已关 WiFi，但调试时有用）

**差距评估**：中等。U1 固件能工作但基础已过时。迁移到 FluidNC 是大工程（固件重写级），但有长期价值。

---

## 二、改善计划（按优先级）

### Tier 1 —— 值得做（解决真实痛点，投入产出比高）

| # | 改进项 | 对标参考 | 痛点 | 工作量 | 风险 |
|---|--------|----------|------|--------|------|
| T1-1 | 意图分类引入语义向量预筛 | Semantic Router | 正则规则维护成本高，新设备场景加规则慢 | 2 天 | 中（需嵌入模型） |
| T1-2 | 路径优化重构为管道架构 | vpype | 路径处理函数耦合，无法独立替换/测试 | 1 天 | 低（纯重构） |
| T1-3 | 字体支持扩展 Hershey 字体 | GRBL-Plotter | 当前仅 fonttools TTF 提取，缺少单笔画字体 | 0.5 天 | 低（新增不破坏现有） |

### Tier 2 —— 可以做（有价值但非紧急）

| # | 改进项 | 对标参考 | 痛点 | 工作量 | 风险 |
|---|--------|----------|------|--------|------|
| T2-1 | U1 固件迁移到 FluidNC | FluidNC | Grbl_Esp32 已停更，无安全更新 | 5-7 天 | 高（固件重写） |
| T2-2 | 后端健康检查探针标准化 | OpenStatus | 健康检查逻辑散在 `health_tracker.py`，无统一探针接口 | 1 天 | 低 |
| T2-3 | 设备任务历史时间线查询 | eventsourcing | 任务历史只能查最终状态 | 2 天 | 中（SQLite schema 变更） |

### Tier 3 —— 暂不做（YAGNI）

| # | 改进项 | 对标参考 | 不做理由 |
|---|--------|----------|----------|
| T3-1 | 后端注册改为 adapter 模式 | LiteLLM | 170+ 后端已稳定运行，dict 模式有效，adapter 模式适合 1000+ 规模 |
| T3-2 | 语义缓存重新引入 | GPTCache | LiMa 已主动退役语义缓存，当前无需求 |
| T3-3 | 完整事件溯源 | eventsourcing | 个人/小团队场景，事件溯源复杂度收益不覆盖成本 |
| T3-4 | 远程证明 | RAVe | ESP32 场景无 SGX 需求，Secure Boot v2 已足够 |

---

## 三、Tier 1 详细设计

### T1-1 意图分类引入语义向量预筛

**问题**：`routing_intent.py` 的 `_ANALYZE_RULES` 有 40+ 条正则，新增设备场景（如「画一只猫」「写你好」）需要手写规则，覆盖面有限，维护成本高。

**方案**：引入双层分类——语义向量预筛（毫秒级）→ 低置信度走 LLM 后备。

**实现步骤**：
1. 新增 `routing_ml/semantic_classifier.py`：
   - 用 `sentence-transformers`（本地嵌入，无需 API 调用）或 OpenAI embedding API
   - 预定义意图→示例句映射（每个意图 3-5 个示例）
   - 余弦相似度匹配，返回 top-1 意图 + 置信度
2. 修改 `routing_intent.py` 的 `analyze_intent`：
   - 先走现有正则规则（快速命中高置信度场景）
   - 正则未命中时，走语义分类器
   - 语义置信度 > 0.85 直接返回；< 0.85 走 LLM 后备
3. 测试：保留现有正则测试，新增语义分类器测试

**参考**：Semantic Router 的 `RouteLayer` + `Encoder` 抽象，但**不直接引入依赖**，用 `sentence-transformers` 或已有 embedding 后端实现。

**验证**：
- 现有 `tests/test_routing_intent.py` 全绿
- 新增 `tests/test_semantic_classifier.py` 覆盖核心意图
- 对比正则 vs 语义分类器的延迟和准确率

### T1-2 路径优化重构为管道架构

**问题**：`svg_converter.py` 的 `image_to_svg_path` 函数内联了下载→二值化→骨架化→追踪→排序→简化→输出的全部步骤，无法独立替换或测试单个阶段。

**方案**：参考 vpype 的管道架构，将路径处理拆为独立阶段。

**实现步骤**：
1. 新增 `xiaozhi_drawing/pipeline.py`：
   ```python
   @dataclass
   class PipelineContext:
       image: np.ndarray | None = None
       polylines: list[Polyline] = field(default_factory=list)
       svg_paths: list[str] = field(default_factory=list)
       metadata: dict = field(default_factory=dict)

   def run_pipeline(image: bytes, stages: list[Callable]) -> str:
       ctx = PipelineContext()
       for stage in stages:
           ctx = stage(ctx)
       return ctx.svg_paths
   ```
2. 将现有函数改为独立 stage：
   - `download_stage` → `binarize_stage` → `skeleton_stage` → `trace_stage` → `order_stage` → `simplify_stage` → `svg_stage`
3. `svg_converter.py` 的 `image_to_svg_path` 改为调用 `run_pipeline`
4. 测试：每个 stage 独立测试，端到端测试保持不变

**参考**：vpype 的 `read → optimize → write` 管道模式。

**验证**：
- 现有 `tests/test_svg_converter.py` / `test_svg_converter_sketch.py` 全绿
- 新增 `tests/test_drawing_pipeline.py` 测试每个 stage

### T1-3 Hershey 字体支持

**问题**：`text_to_path.py` 用 fonttools 从 TTF 提取字形轮廓，但 TTF 字形是闭合轮廓（双线），绘图机会画出双线。Hershey 字体是单笔画字体，天然适合绘图机。

**方案**：新增 Hershey 字体解析器，作为 TTF 的补充选项。

**实现步骤**：
1. 新增 `xiaozhi_drawing/hershey_font.py`：
   - 解析 Hershey 字体数据（公众域，jhf 格式）
   - 将 Hershey 字符转换为 SVG path
2. 修改 `text_to_path.py`：
   - 新增 `font_type` 参数（"ttf" | "hershey"）
   - hershey 模式调用 `hershey_font.py`
3. 预置 Hershey 字体数据到 `xiaozhi_drawing/fonts/hershey/`

**参考**：GRBL-Plotter 的 Hershey 字体支持；[Hershey 字体原始数据](https://en.wikipedia.org/wiki/Hershey_fonts)。

**验证**：
- 新增 `tests/test_hershey_font.py`
- 端到端：文字→Hershey 路径→SVG→GCode→绘图机

---

## 四、执行顺序

```
第 1 周：T1-2 路径管道重构（低风险先行，纯重构不改行为）
第 2 周：T1-3 Hershey 字体（增量新增，不破坏现有）
第 3 周：T1-1 语义分类器（中风险，需嵌入模型，TDD 必须）
```

每项独立 commit 可回滚；T1-1 必须 TDD；每项完成后更新 STATUS/progress/findings。

---

## 五、不做的事（YAGNI 边界）

- ❌ 不重写后端注册系统（170+ 后端已稳定）
- ❌ 不重新引入语义缓存（已主动退役）
- ❌ 不做完整事件溯源（复杂度不匹配场景）
- ❌ 不迁移 U1 到 FluidNC（Tier 2，需用户确认产品方向后再定）
- ❌ 不引入 LiteLLM 作为依赖（LiMa 的路由管线有自己的 18 步设计）

---

## 六、风险与回滚

| 风险 | 缓解 |
|------|------|
| 语义分类器引入新依赖（sentence-transformers） | 先用 OpenAI embedding API（已有后端），避免本地模型依赖 |
| 管道重构破坏现有绘图行为 | 每个 stage 保持现有函数签名，端到端测试不变 |
| Hershey 字体数据版权 | Hershey 字体为公众域，无版权风险 |
| 嵌入模型增加启动延迟 | 懒加载，首次使用时初始化，不影响启动 |

通用回滚：每项独立 commit，`git revert <sha>` 即可。
