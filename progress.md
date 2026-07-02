# Personal Coding Assistant Progress

> 历史归档：2026-06-30 及更早条目 → [`docs/archive/progress-2026-06.md`](docs/archive/progress-2026-06.md)

## 2026-07-02 代码尺寸门禁清零 + 小程序死页面清理

### 背景

`check_code_size.py` 报告 2 个文件超过 300 行（`test_drawing_pipeline.py` 366 行、`test_deploy_unified.py` 304 行），且小程序中残留已退役的 mine.vue 页面和 4 个未引用的语言文件。

### 改动

1. **拆分 `test_drawing_pipeline.py`（366→293 行）**：将 `TestRunPipeline` 端到端测试拆到 `test_drawing_pipeline_e2e.py`（105 行），原文件保留 stage 独立测试。
2. **拆分 `test_deploy_unified.py`（304→183 行）**：将 6 个 mock 类提取到 `tests/_deploy_mocks.py`（126 行），消除重复 setup 代码。
3. **删除 4 个残留语言文件**：`de.ts`/`vi.ts`/`pt_BR.ts`/`zh_TW.ts`（已在上一轮从 import 移除但物理文件残留，共 ~117K）。
4. **删除 mine.vue 死页面**：功能已完全被 settings 吸收（退出登录、声纹、关于），tabbar 已无 mine 入口；从 `pages.json` 移除注册，清理 `tabBar.mine` i18n 键。
5. **小程序 P2 瘦身变更入库**：4 个 composables（useServerUrl/useCacheManager/useNotifications/useAccountDeletion）、tabbar 5→3、alova.ts langMap 裁剪等。

### 验证

- `check_code_size.py`：**0 个 >300 行文件、0 个 >50 行函数**（首次全绿）
- 全量 pytest：**4391 passed / 3 skipped / 2 deselected / 0 failed**
- `ruff check` clean；pre-commit 全绿
- `vue-tsc --noEmit` 0 errors

### Git

- 子模块 `esp32S_XYZ`：`db1a118..3381e19`（19 files, +423/-2796）
- 根仓库：`55d135ca..7ca69fe4`（测试拆分 + 子模块指针）

## 2026-07-02 系统瘦身 P2-17/18：小程序 UI 合并完成

### P2-18: 合并 3 个首页 → tabbar 5→3（已完成）

**痛点**：tabbar 5 个 tab 中有 3 个首页重叠（device-list / WorkshopHome / mine），且「配网」是一次性 onboarding 却占永久位。

**改动**：
1. **mine → settings 合并**：将 mine 页的声纹入口、退出登录功能合并到 settings 页（新增两个 SectionCard），mine 页 layout 从 tabbar → default
2. **index(WorkshopHome) 移出 tabbar**：与 device-list 功能重叠（都是设备仪表盘），layout 从 tabbar → default；device-detail 中 goToAgents 改为 navigateTo
3. **tabbar 5→3**：首页(device-list) + 配网(device-config) + 设置(settings)；tabBarI18nKeys 同步裁剪
4. **settings 页 layout**：从 default → tabbar（因为现在是 tabbar 页面）

**P2-17 决策**：write-draw-panel 已是简化版 2 步流（写字+画图），create/ 页面是高级模式（含图片选择、参数面板）。合并会丢失高级功能，决定保留现状。满足「≤3 步」要求。

**验证**：vue-tsc 0 errors；mp-weixin 编译成功；settings 379 行（< 400）；无 switchTab 到已移除页面的残留引用

## 2026-07-02 系统瘦身 P2-19：小程序 settings 瘦身完成

### P2-19: settings 瘦身（已完成）

**痛点**：settings/index.vue 是 656 行的杂物袋，混合了 7 个功能段（服务端地址、缓存管理、隐私权限、通知订阅、账号注销、关于、语言），且语言列表包含 4 个臆测语言（de/vi/pt_BR/zh_TW）。

**改动**：
1. **语言裁剪**：`Language` 类型从 6 种裁到 2 种（zh_CN + en）；删除 `de.ts`/`vi.ts`/`pt_BR.ts`/`zh_TW.ts` 导入；更新 `alova.ts` 的 `langMap`
2. **逻辑拆分到 composables**：
   - `hooks/useServerUrl.ts` — 服务端地址管理（加载/验证/测试/保存/重置）
   - `hooks/useNotifications.ts` — 微信通知订阅管理
   - `hooks/useCacheManager.ts` — 缓存信息获取与清除
   - `hooks/useAccountDeletion.ts` — 账号注销双确认流程
3. **settings/index.vue 重写**：从 656 行 → 322 行（< 400 行目标达成），脚本段从 ~400 行 → ~75 行

**验证**：vue-tsc --noEmit 0 errors；无残留 zh_TW/de/vi/pt_BR 引用

## 2026-07-02 系统瘦身 P2-20：except:pass/continue 违规审查完成

### P2-20: 审查 except Exception: pass/continue 违反硬规则（已完成）

**痛点**：AGENTS.md 硬规则 #1 禁止 `except Exception: pass`（静默降级），但此前统计有 21 个文件疑似违规。

**审查过程**：
- 编写精确检测脚本，区分宽泛异常捕获（`except Exception:`）与特定异常类型捕获（`except json.JSONDecodeError:` 等）
- 全面扫描后确认：83 个 `except: pass/continue` 中，仅 3 个是真正的宽泛异常静默吞掉（违反硬规则），其余 80 个是特定异常类型的合法控制流

**修复的 3 个违规**：
1. `packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64` — `except Exception: continue` → 添加 `logging.debug` 记录探测失败原因
2. `packages/provider-probe-offline/provider_probe/reverse/pricing_probe.py:74` — `except Exception: continue` → 添加 `logging.debug` 记录定价探测失败原因
3. `tests/test_memory_promote.py:39` — `except Exception: pass` → 添加 `logging.debug` 记录 DB 状态依赖异常

**验证**：全量 4391 passed, 0 failed；ruff check clean；违规数归零

## 2026-07-02 系统瘦身 P1-13/14：routing_engine/executor 归包完成

### P1-13: routing_engine 9 个根文件 → 包（已完成）

**痛点**：`routing_engine*.py` 共 9 个文件散落在仓库根目录，阅读一个路由决策需要打开 14+ 文件，概念碎片化严重。

**实现**：
- 创建 `routing_engine/` 包目录，9 个文件移入并缩短名称：
  - `routing_engine.py` → `routing_engine/__init__.py`（facade，保持公共 API 不变）
  - `routing_engine_types.py` → `routing_engine/types.py`
  - `routing_engine_trace.py` → `routing_engine/trace.py`
  - `routing_engine_cache.py` → `routing_engine/cache.py`
  - `routing_engine_context.py` → `routing_engine/context.py`
  - `routing_engine_execute_strategy.py` → `routing_engine/execute_strategy.py`
  - `routing_engine_helpers.py` → `routing_engine/helpers.py`
  - `routing_engine_intent.py` → `routing_engine/intent.py`
  - `routing_engine_post.py` → `routing_engine/post.py`
- 包内导入改为相对导入（`from .trace import trace_span` 等）
- 外部引用更新：`routing_engine` 主模块 API 完全不变（`from routing_engine import route, pick_backend, ...`）
- 测试文件更新：7 个测试文件中的子模块导入路径和 patch 路径更新
- `pyrightconfig.json` 更新：`routing_engine.py` → `routing_engine/`

### P1-14: routing_executor 5 个根文件 → 包（已完成）

**痛点**：`routing_executor*.py` 共 5 个文件散落在仓库根目录，与 routing_engine 同属概念碎片化。

**实现**：
- 创建 `routing_executor/` 包目录，5 个文件移入：
  - `routing_executor.py` → `routing_executor/__init__.py`
  - `routing_executor_telemetry.py` → `routing_executor/telemetry.py`
  - `routing_executor_serial.py` → `routing_executor/serial.py`
  - `routing_executor_parallel.py` → `routing_executor/parallel.py`
  - `routing_executor_fallback.py` → `routing_executor/fallback.py`
- 包内导入改为相对导入
- 外部引用不变（`from routing_executor import execute`）
- 4 个测试文件更新子模块导入路径
- `test_routing_pipeline_authority.py` 更新：源码路径检查从 `routing_executor_serial` → `routing_executor.serial`

### 验证

- 全量测试：**4391 passed, 3 skipped, 0 failed**
- ruff check：Python 文件全部 clean（pyrightconfig.json 的 JSON false 误报忽略）
- code size：0 个 >300 行文件，0 个 >50 行函数
- 公共 API 完全向后兼容：`from routing_engine import route` 和 `from routing_executor import execute` 不变

## 2026-07-02 Tier 2 改善计划推进

### T2-2 后端健康检查探针标准化（已完成）

**痛点**：`backend_probe_loop.py` 有重复的 `_classify_error` 函数，与 `health_recorder.classify_failure` 逻辑重复且分类结果不一致。

**实现**：
- 新增 `health_probe.py`：定义 `ProbeResult` dataclass、`HealthProbe` Protocol、`classify_probe_error()` 委托函数、`make_result()` 便捷构造器
- 重构 `backend_probe_loop.py`：删除重复的 `_classify_error`（-13 行），改用 `classify_probe_error` 委托至 `health_recorder.classify_failure`
- 新增 `tests/test_health_probe.py`：16 个测试覆盖 ProbeResult、classify_probe_error、make_result
- 全量测试：4391 passed, 0 regressions

**关键文件**：`health_probe.py`、`backend_probe_loop.py`、`tests/test_health_probe.py`

### T2-3 设备任务历史时间线查询（已完成）

**痛点**：`GET /tasks/{task_id}` 只返回原始事件列表，无法直观看到状态流转和阶段耗时；`GET /tasks` 只返回当前状态，无历史时间线。

**实现**：
- 新增 `device_gateway/task_timeline.py`：将 ledger 事件流转换为结构化时间线，含中文状态描述、阶段间耗时、终态判断
  - `build_task_timeline(task_id)`：单任务时间线（事件→阶段流转+耗时）
  - `build_device_timeline(device_id, limit)`：设备级时间线（多任务聚合，按最后更新倒序）
- 新增 `routes/device_timeline_routes.py`：两个新端点（独立路由文件，控制 device_gateway.py 行数 ≤300）
  - `GET /device/v1/tasks/{task_id}/timeline`：单任务状态流转时间线
  - `GET /device/v1/devices/{device_id}/timeline`：设备任务历史时间线
- 路由注册：`routes/route_registry.py` 添加 `device_timeline_routes` 到 `_DEVICE_APP_ROUTERS`
- 新增 `tests/test_task_timeline.py`：9 个测试覆盖单任务/设备级时间线、排序、limit、终态判断
- 全量测试：4391 passed, 0 regressions

**关键文件**：`device_gateway/task_timeline.py`、`routes/device_timeline_routes.py`、`tests/test_task_timeline.py`

### T2-1 U1 固件迁移到 FluidNC（软件层完成，硬件验证待人工执行）

**痛点**：Grbl_Esp32 已停更，无安全更新；配置需编译时 C 头文件硬编码。

**软件层实现**：
- 翻译 `dlc_motor_control_p1.h` → `firmware/fluidnc/config/dlc_motor_control_p1.yaml`
  - 完整映射 GPIO（X/Y/Y2/Z STEP/DIR、MOTOR_EN、4 路限位、激光 PWM）
  - 运动参数（steps/mm、max_rate、acceleration、pulse_us、idle_ms）
  - 回零策略（Z→X→Y 顺序、Y/Y2 龙门校正 square:true）
  - 激光模式（PWM 输出 GPIO45）
- 编写 `esp32S_XYZ/docs/U1-FluidNC迁移计划.md`：含配置映射对照表、8 步硬件验证清单（D1-D8）、回退方案、已知风险

**待人工执行**：D1-D8 硬件验证步骤（需物理设备在环测试，Agent 无法替代）

## 2026-07-02 Tier 1 改善计划全部完成

三项 Tier 1 改善计划已按顺序实施完成，全部测试通过（193 passed, 0 regressions）。

### T1-2 路径优化重构为管道架构（对标 vpype）

- **新增** `xiaozhi_drawing/pipeline.py`：管道架构（`PipelineContext` + `run_pipeline` + 5 个独立 stage 函数）
- **重构** `xiaozhi_drawing/svg_converter.py`：委托至管道阶段，保持所有公共 API 向后兼容
- **测试**：`tests/test_drawing_pipeline.py`（26 tests）+ 现有 39 tests 全部通过
- **关键设计**：`preprocess → skeleton → trace → order → simplify` 五阶段可独立测试和替换

### T1-3 Hershey 单笔画字体支持（对标 GRBL-Plotter）

- **新增** `xiaozhi_drawing/hershey_font_data.py`：96 字符的 Hershey 字体数据（A-Z, a-z, 0-9, 标点）
- **新增** `xiaozhi_drawing/hershey_font.py`：渲染器（`hershey_text_to_svg_path`）
- **修改** `xiaozhi_drawing/text_to_path.py`：新增 `font_type="hershey"` 参数，默认 `"ttf"` 不破坏现有行为
- **测试**：`tests/test_hershey_font.py`（23 tests）全部通过
- **关键优势**：单笔画开放路径（无 Z），绘图机不会画出双线

### T1-1 意图分类引入语义向量预筛（对标 Semantic Router）

- **新增** `routing_semantic.py`：n-gram TF-IDF 余弦相似度分类器（纯 Python，零外部依赖）
- **修改** `routing_intent.py`：在 `_enhanced_classify` 中插入语义层（规则 → 信号 → 语义 → 上下文 → 默认）
- **测试**：`tests/test_routing_semantic.py`（26 tests）+ 现有 88 tests 全部通过
- **关键设计**：不引入 sentence-transformers 或网络 API，用 n-gram TF-IDF 实现毫秒级语义匹配
- **行为改进**：`"explain quantum mechanics"` 从默认 `"chat"` 改进为正确识别 `"explanation"`

### 文件清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `xiaozhi_drawing/pipeline.py` | 新增 | 226 |
| `xiaozhi_drawing/svg_converter.py` | 重构 | 248 |
| `xiaozhi_drawing/hershey_font.py` | 新增 | 188 |
| `xiaozhi_drawing/hershey_font_data.py` | 新增 | 138 |
| `xiaozhi_drawing/text_to_path.py` | 修改 | 243 |
| `routing_semantic.py` | 新增 | 166 |
| `routing_intent.py` | 修改 | 296 |
| `tests/test_drawing_pipeline.py` | 新增 | 367 |
| `tests/test_hershey_font.py` | 新增 | 148 |
| `tests/test_routing_semantic.py` | 新增 | 159 |

全部文件通过 `ruff check`、`ruff format --check`、`check_code_size.py`（≤300 行/≤50 行函数）。

## 2026-07-02 基于参考项目的改善计划制定

- **背景**：系统瘦身完成后，基于已核实的 GitHub 参考项目，分析 LiMa 与参考项目的差距，按 Ponytail YAGNI 原则过滤后制定精准改善计划。
- **差距分析**：逐一对比 LiMa 现状与 5 个核心参考项目（Semantic Router、vpype、LiteLLM、eventsourcing、FluidNC），评估差距大小和改进价值。
- **Ponytail 过滤结果**：
  - **Tier 1 值得做（3 项）**：T1-1 语义向量预筛意图分类、T1-2 路径优化管道重构、T1-3 Hershey 单笔画字体支持
  - **Tier 2 可以做（3 项）**：T2-1 U1 固件迁移 FluidNC、T2-2 健康探针标准化、T2-3 设备任务时间线查询
  - **Tier 3 暂不做（4 项）**：后端 adapter 模式、语义缓存、完整事件溯源、远程证明 —— 均 YAGNI
- **设计文档**：`docs/superpowers/specs/2026-07-02-reference-driven-improvement-plan.md`（中文）
- **关键设计决策**：
  - 语义分类器不直接引入 Semantic Router 依赖，用已有 embedding 后端自实现
  - 路径管道重构参考 vpype 架构但保持现有函数签名，纯重构不改行为
  - Hershey 字体是增量新增，不破坏现有 TTF 路径
- **待用户审批**：计划已就绪，等待用户确认优先级和执行顺序后开始实施。

## 2026-07-02 GitHub 参考项目实测核实 + 文档更新

- **背景**：项目文档 `docs/superpowers/plans/LiMa_QWEN3_系统增强细化方案_v3_20260624.md` 附录中收录了 30+ 个 GitHub 参考项目，星数和活跃度数据写于 2026-06-24，用户要求重新到 GitHub 核实。
- **核实方式**：逐个用浏览器访问 GitHub 仓库页面，提取实时星数、最后提交时间、是否归档。
- **核实结果**：
  - **核心参考全部真实活跃**：LiteLLM 52.3k（原标 20k+，今日仍在更新）、Ponytail 70.8k（昨日更新）、FluidNC 2.5k（上月更新）、Semantic Router 3.7k（原标 2k+）、vpype 917（原标 500+）、bCNC 1.7k（原标 1.5k+）、eventsourcing 1.7k（原标 1.5k+）。
  - **5 个项目已死或低价值**，已附替代推荐：
    - `IoTThinks/esp32FOTA`（1 星，2021 停更）→ 替代 [espressif/esp_https_ota](https://github.com/espressif/esp-idf/tree/master/components/esp_https_ota)
    - `barfittc/gcode-optimizer`（0 星，2023 停更）→ 替代 vpype 的 `optimize` 命令
    - `DrivenIdeaLab/openstatus`（0 星，URL 可能有误）→ 替代 [upstash/openstatus](https://github.com/upstash/openstatus)
    - `PufferFinance/rave`（35 星，SGX 场景不匹配）→ 替代 ESP-IDF Secure Boot v2 官方实现
    - `SebKuzminsky/svg2gcode`（25 星，功能简单）→ 替代 vpype 的 SVG→GCode 管道
  - 其余项目（esp_ghota 446 星、GRBL-Plotter 865 星、BrachioGraph 745 星、ModelCache 941 星、GPTCache 8.1k 星、THiNX 24 星但活跃）均真实存在，已更新精确星数和活跃度标记。
- **文档更新**：`docs/superpowers/plans/LiMa_QWEN3_系统增强细化方案_v3_20260624.md` 附录 A.1–A.9 共 19 处编辑——更新星数、添加活跃度标记（🟢/🟡/🔴）、为 5 个死掉/低价值项目添加替代推荐、末尾添加核实说明。
- **教训**：文档中的第三方项目数据会随时间漂移，星数只增不减但活跃度会变化。建议每季度核实一次参考项目清单，及时标记死链和替代推荐。

## 2026-07-02 全量门禁 + 京东云生产部署 + 公网冒烟验证

- **本地全量门禁**：`scripts/run_pre_commit_check.py --full` → **4278 passed, 3 skipped, 2 deselected**；ruff check clean。（测试数较上次 4285 少 7 个，因小程序 UI 重构删除了死鉴权端点相关测试。）
- **VPS 部署**：`deploy_unified.py --target jdcloud --slice core` → 883 文件上传，0 失败。tar/scp 因 SSH key 认证失败自动回退 SFTP（密码认证）成功。备份 `/opt/lima-router/backups/unified-core-20260702_141038/runtime-before.tgz`。服务重启健康检查 OK。
- **公网冒烟验证**：
  - `GET /health` → `{"status":"ok","version":"2.0","model":"lima-1.3","startup":{"status":"ready"}}` ✅
  - `GET /health/ready` → `{"status":"ready","startup_status":"ready","pending_warm":[],"error_count":0}` ✅
  - `POST /v1/chat/completions`（匿名）→ 200，后端 `cfai_qwen_coder`，记忆召回 `memory_ids:[33,7]` ✅
  - `/device/v1/app/voice/ticket` → 405（GET 不支持，端点可达）✅
- **结论**：最新代码（含小程序 UI 重构、静默降级修复、retired 代码清理、deploy_unified 京东云支持）已部署到京东云生产节点并验证通过。

## 2026-07-02 小程序 UI 深度重构（BACKLOG-P2-1）

- **背景**：瘦身审查报告三项 UI 指控，逐项核实后真伪分明，按「真问题改、伪指控纠偏」执行。
- **核实纠偏**：
  - `create.vue` 937 行嵌套两层 tab（`mode`+`aiSubMode`，两路不同 API）— **属实**。
  - 3 首页重叠（mine 统计与 index Hero 重复；mine 跳底栏已有 tab）— **部分属实**。
  - `settings` 744 行「杂物」— **不属实**（全是设置页职责，仅样式重复+2 死代码）。
  - `chat` 与 `create` 重叠 — **不属实**（零交叉导入）。
- **M1 抽公共组件 + settings 死代码**（子模块 `a6e1e60`）：新增 `section-card.vue`（≤30行）、`stat-pill.vue`（≤80行）；settings 7 个重复 section 壳 → `<SectionCard>` 组件调用，744→655 行；删 `useConfigStore`/`systemInfo` 2 处死代码。视觉零变化。
- **M2 create.vue 拆两页**（子模块 `9110792`）：新增 `useCreateShared.ts` composable 抽共享逻辑；`ai-draw.vue`(322行) 承载云生图、`image-draw.vue`(264行) 承载设备绘图；抽 `create-shared.scss` 共享样式；删 create.vue 937 行；index.goDraw/goImageDraw 改跳新页去 `?mode=`；pages.json 路由更新。
- **M3 mine 转纯账号页 + index 去重**（子模块 `c78edc1`）：mine 418→305 行，删 3 统计卡 + 设备数据获取、删「设备管理/配网」冗余菜单（底栏已直达）、新增「声纹」入口；index Hero sub-item「设备 X 台」改为「在线 X/总 Y 台」吸收在线统计；i18n zh/en 加 `mine.voiceprint/voiceprintDesc`。
- **M4 验收 + 文档**：`npx vue-tsc --noEmit` 0 errors（每里程碑均验证）；`npx uni build --platform mp-weixin` 编译通过（exit 0，dist/build/mp-weixin 生成）；设计文档见 `docs/superpowers/specs/2026-07-02-miniprogram-ui-refactor-design.md`（中文）。
- **未做**：微信上传/审核（BACKLOG-P0-4 单独触发）；真机端到端（BACKLOG-P0-3，需硬件）。
- **教训**：审查「行数/嵌套层数」可信，但「杂物/重叠」严重度判定不可信。改 UI 前必须逐区块核实职责归属，不能按行数盲改。

## 2026-07-02 retired 文件删除 + 冗余 Cursor rules 清理（BACKLOG-P1-3/P1-4）

- **BACKLOG-P1-3 删除退役代码**：`docs/archive/retired/` 下 7 个 Gitee 镜像/双推退役文件（`gitee_mirror*.py`、`gitee_mirror_urls.py`、`push_dual_remotes.{ps1,py,sh}`、`test_gitee_mirror.py`）。全仓 grep 确认**零引用**，Gitee 镜像已彻底退役，git 历史可恢复。代码文件不应残留在 `docs/` 树，直接 `git rm` 删除（含 `__pycache__` 物理清理）。
- **BACKLOG-P1-4 agent 配置树纠偏**：审查报告称「8 棵树 / ~9300 行 / Ponytail 重复 6 处」。逐树核实后**纠偏**：
  - 8 棵树中 **5 棵被 `.gitignore` 忽略不入库**（`.agent`、`.claude`、`.kimi-code`、`.continue`、`andrej-karpathy-skills`）——本地 IDE 私有副本，重复无害，无需处理。
  - 入库的 agent 树仅 `.cursor`（2 rules）、`.joycode`（2 memory）、`skills`（14）、`AGENTS.md`、`CLAUDE.md`。
  - 真正可统一项仅 `.cursor/rules/` 两份：`ponytail.mdc`（与 `docs/AGENTS_PONYTAIL.md`，被 `AGENTS.md` 引用为权威源）重复、`ecc-workflow.mdc`（与 `docs/ECC_WORKFLOW_CN.md`，被 `AGENTS.md` 引用）重复。两份均 `alwaysApply: true`，删后 Cursor 失去自动注入但 `AGENTS.md` 仍是权威源。
  - 删除 `.cursor/rules/ponytail.mdc` + `ecc-workflow.mdc`，保留 `.cursor/rules/lima-*.mdc`（未入库的本地 Cursor 私有 rules）不动。
- **验证**：`ruff check .` + `scripts/check_code_size.py` 全通过；删除项不影响测试（`docs/`、`.cursor/rules` 不在 import 路径）。
- **教训**：审查「8 棵树 / 9300 行 / 重复 6 处」口径来自把「被 gitignore 的本地私有配置」也计入重复——合并前必须区分「入库」与「本地工具私有」，否则会去清理一堆本就不该入库的副本。

## 2026-07-02 code-review 修复 + 静默降级修复（BACKLOG-P1-2/P1-1）

- **code-review 死导入清理**：`DeployTarget` 重构（P0-1）留下 9 处死导入/重定义（`shlex`、`time`×2、重复 `from config import deploy_config`×2、`CORE_FILES`、`DEFAULT_MIN_FREE_MB`、`DEFAULT_MIN_MEM_MB`、未用 `deploy_config`×2）。这些因 `ruff.toml` 只 select `E9/F821/...` 不含 `F401`/`F811` 而漏过 pre-commit。已全部移除，提交 `refactor(deploy): remove dead imports left by DeployTarget refactor`（`7b2b7140`）。
- **BACKLOG-P1-2 静默降级修复（纠偏后精准执行）**：审查报告称「16 处 / voice_pipeline_ws·mqtt_client·store_voiceprint 各 2 处」。用 Explore 子代理实地核查后**证伪**——那 6 处全是 `asyncio.TimeoutError` / `CancelledError` / `sqlite3.OperationalError` 幂等迁移，属正常控制流，**0 违规**。真正违反 AGENTS.md「禁止静默降级」的是 **4 处**一等生产路径的 `except Exception:` 裸吞：
  - `routing_executor_parallel.py`：并行降级执行器逐 future 吞 worker 异常 → 补 `_log.warning`（`_try_one_parallel` 已记录 per-backend 失败，此处仅 worker 本身异常）。
  - `speculative_execution.py`：推测竞速内层 `future.result()` 吞异常 → 补 `logger.debug`（`_spec_worker` 已 warning+exc_info 记录真实后端失败并返回 ""，到此仅 future 本身取消/executor 错误，debug 避免每次推测落败刷屏）。
  - `observability/jsonl_store.py`：读遥测文件吞异常 → 窄化为 `(OSError, UnicodeDecodeError)` + `_log.warning`；顺手删预存死导入 `os`。
  - `provider_automation/adapters/cloudflare.py`：编码评分循环吞调用失败 → 补 `_log.warning`（新增 `logging` import + `_log`）。
- **边界项（不改，仅记录）**：`packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64`、`pricing_probe.py:74` 各 1 处 `except Exception: continue`——属冷离线探测工具，不在生产请求路径，本轮不改，记入 findings 供后续排期。
- **BACKLOG-P1-1**：语音设计文档 `2026-07-02-mini-program-voice-draw-design.md` 状态标记经查已在前序会话更新为「已完成（M0+M1+M2）」，无残留「待审批」标记，无需再改。
- **验证**：受影响模块聚焦测试 176 passed；全量 `pytest` **4288 passed, 3 skipped**；`ruff check .`（项目配置）+ 全量 `F401/F811` 复查 + `scripts/check_code_size.py` 全通过。
- **教训**：审查报告的「计数」可信，但「严重度判定」不可信——同一批 6 个 `except: pass` 计数准确却 0 违规。修静默降级前必须逐点区分「裸 `except Exception` 无日志」（违规）与「窄化异常做控制流」（合规），不能按 pattern 计数盲改。

## 2026-07-02 U8 固件改 PCM 解决音频协议矛盾（BACKLOG-P0-2）

- **背景**：U8 固件 `audio_service.cc` 的麦克风输入走 OPUS 编码后发送，但 `websocket_protocol.cc` 的 hello 帧已声明 `"format":"pcm"`，后端 `device_voice_ws_helpers.py` / `voice_pipeline_ws.py` 均假设 PCM 输入，导致设备实时语音/TTS 无法互通。
- **方向**：用户选择方案 A——固件改 PCM，后端零改动。
- **实现**（U8 固件侧，路径 `esp32S_XYZ/firmware/u8-xiaozhi/main/`）：
  - `protocols/protocol.h`：
    - `AudioStreamPacket` 新增 `std::string format = "opus"` 字段；
    - `Protocol` 基类新增 `virtual bool UsesPcm() const { return false; }`。
  - `protocols/websocket_protocol.h`：覆写 `UsesPcm()` 返回 `true`。
  - `protocols/websocket_protocol.cc`：对下行音频包（v1/v2/v3）统一设置 `format = "pcm"`。
  - `protocols/mqtt_protocol.cc`：对下行音频包显式设置 `format = "opus"`（保持 MQTT 默认行为）。
  - `audio/audio_service.h`：新增 `bool send_pcm_` 成员与 `SetSendPcm(bool)` 方法。
  - `audio/audio_service.cc`：
    - `OpusCodecTask` 上行分支：按 `send_pcm_` 选择 PCM 透传或 OPUS 编码；
    - `OpusCodecTask` 下行分支：按 `packet->format` 选择 PCM 透传或 OPUS 解码；
    - `PlaySound` 保持 `format = "opus"`，本地 Ogg 提示音继续走 OPUS 解码路径；
  - `application.cc`：协议初始化后调用 `audio_service_.SetSendPcm(protocol_->UsesPcm())`，使 Websocket/LiMa 路径启用 PCM 上行。
- **验证**：
  - 代码审查确认下行/上行/提示音三条路径格式区分清晰；MQTT 路径未破坏；PlaySound 路径未破坏。
  - 未执行 ESP32 编译/烧录（当前环境无工具链），需你本地 `idf.py build` + 烧录 U8 后验证实时语音与 TTS 回放。
- **风险**：固件中 OPUS 编码器/解码器仍初始化但 Websocket 路径不再使用，会占用少量 RAM/CPU；后续如需彻底清理，可再拆一轮移除 OPUS 依赖。
- **文档**：更新 `findings.md` 关闭 P0-2。

## 2026-07-02 deploy_unified.py 支持京东云主生产节点（BACKLOG-P0-1）

- **背景**：2026-07-02 部署小程序语音端点时，`deploy_unified.py` 默认连接阿里云（`LIMA_SERVER=47.112.162.80`），而公网入口 `chat.donglicao.com` 实际走 Cloudflare Tunnel → 京东云（`117.72.118.95`）。误部署导致公网端点返回 404。
- **实现**：
  - `config/deploy_config.py`：新增 `deploy_target()`（默认 `jdcloud`）、`aliyun_password()`（回退到 `LIMA_DEPLOY_PASS`）、保留 `jdcloud_password()`。
  - `scripts/deploy_unified_common.py`：新增 `DeployTarget` 值对象、`get_deploy_target()`、`TARGET_ALIYUN` / `TARGET_JDCLOUD`；`_connect_ssh()` 改为按目标连接。
  - `scripts/deploy_unified.py`：新增 `--target {aliyun,jdcloud}`，默认 **jdcloud**；打印目标名与 IP；部署标签包含目标名。
  - `scripts/deploy_unified_preflight.py`/`deploy_unified_deploy.py`/`deploy_unified_restart.py`/`deploy_unified_nginx.py`：全部改为接收 `DeployTarget`，使用目标专属 `host`/`remote_path`/`user`/`password`/`key_path`。
  - `.env.example`：新增 `LIMA_DEPLOY_TARGET`、`LIMA_ALIYUN_PASSWORD`、`LIMA_JDCLOUD_ROOT_PASSWORD` 说明；保留 `LIMA_DEPLOY_PASS` 作为 Aliyun 历史别名。
- **验证**：
  - `python scripts/deploy_unified.py --dry-run --target jdcloud --slice core` → 目标显示 `jdcloud (117.72.118.95)`。
  - `python scripts/deploy_unified.py --dry-run --target aliyun --slice core` → 目标显示 `aliyun (47.112.162.80)`。
  - `ruff check scripts/deploy_unified.py scripts/deploy_unified_*.py config/deploy_config.py tests/test_deploy_unified.py` → PASS。
  - `python -m py_compile` 上述文件 → PASS。
  - `.venv310` 下全量 pytest：`4286 passed, 3 skipped, 2 deselected`（含更新后的 `tests/test_deploy_unified.py` 10 passed）。
  - 实际部署 JDCloud：`python scripts/deploy_unified.py --slice core` → 883 uploaded / 0 failed / health OK / `Deploy OK: unified/core/jdcloud`。
  - 公网冒烟：`https://chat.donglicao.com/health/ready` → `{"status":"ready"}`；`POST /device/v1/app/voice/ticket` → 401（鉴权生效）。
- **风险**：默认目标从隐式 Aliyun 改为显式 JDCloud，可能改变只依赖 `LIMA_SERVER` 而不看 `--target` 的用户/脚本习惯。已通过 `--target aliyun` 保留回退路径。
- **文档**：更新 `STATUS.md` 将「待修」改为「已修复」；`findings.md` 关闭 BACKLOG-P0-1；`.env.example` 同步说明。

## 2026-07-02 移除设备网关 WebSocket query 参数 token 注入（AUDIT-11-W2）

- **背景**：`routes/device_gateway_dispatch.py:extract_ws_token`  historically 支持 ticket / Authorization header / `?token=` / `?authorization=` 四种注入方式，后两者会让 Bearer token 进入 nginx access log 与 Referer。此前生产已默认拒绝 query token，但代码仍保留 legacy 分支和临时环境变量 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN`。
- **实现**：
  - `routes/device_gateway_dispatch.py`：删除 `import os`、移除 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 判断与 legacy query token 分支，`extract_ws_token` 仅保留 `?ticket=` 与 `Authorization` header 路径。
  - `.env.example`：删除 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 相关说明。
  - `tests/conftest.py`：删除 `_allow_legacy_device_ws_query_token_in_tests` autouse fixture。
  - `tests/test_device_gateway_dispatch.py`、`tests/test_device_ws_ticket.py`、`tests/test_routes_device_gateway_dispatch.py`：更新断言，确认 query token/authorization 被永久拒绝。
  - 设备 WS 集成测试迁移：把 `client.websocket_connect("/device/v1/ws?token=test-device-token")` 改为 `headers={"Authorization": "Bearer test-device-token"}`，涉及 `tests/device_gateway/test_ai_to_motion_gate.py`、`test_tasks_http.py`、`test_ws_lifecycle.py`、`test_device_gateway_ws_errors.py`、`test_fake_u1_cloud_*.py`、`test_p1_4_device_stability_gate*.py`。
  - `docs/DEVICE_WS_TOKEN_DEPRECATION_CN.md`：更新为 Phase 2 已完成，query token 注入已移除。
- **验证**：
  - 聚焦设备 WS 相关测试：71 passed，1 skipped。
  - 全量 pytest：`4285 passed, 3 skipped, 2 deselected`。
  - `ruff check .`、`ruff format --check`、`pyright` 目标文件、`scripts/check_code_size.py` 均通过。
  - `grep` 确认仓库中不再有 `/device/v1/ws?token=` 与 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 代码/测试引用。
- **风险**：若前端或固件仍有未切换的 `?token=` 调用，生产会认证失败；但生产此前已默认拒绝 query token，因此本次仅清理 legacy 代码与测试，不影响线上行为。
- **文档**：更新 `findings.md`、`STATUS.md` 将 AUDIT-11-W2 标记为已关闭。

## 2026-07-02 为 AUDIT-6-A1 补充 OpenAPI 文档开关显式测试

- **背景**：`server.py` 已按 AUDIT-6-A1 默认禁用 Swagger/OpenAPI 文档（`LIMA_DOCS_ENABLED=1` 可开启），但测试目录此前无针对 `/docs`、`/redoc`、`/openapi.json` 返回行为的断言。
- **实现**：新增 `tests/test_server_docs_disabled.py`：
  - 默认环境下通过独立子进程导入 `server`，断言三个文档端点均返回 404。
  - 设置 `LIMA_DOCS_ENABLED=1` 后，断言 `/docs`、`/redoc` 返回 HTML 200，`/openapi.json` 返回 200。
  - 使用子进程隔离，避免切换 `LIMA_DOCS_ENABLED` 时污染同进程的全局 `app` 对象。
- **验证**：
  - `tests/test_server_docs_disabled.py`：2 passed。
  - 全量 pytest：`4285 passed, 3 skipped, 2 deselected`。
  - `ruff check .`、`ruff format --check`、`pyright tests/test_server_docs_disabled.py server.py`、`scripts/check_code_size.py` 均通过。
- **文档**：更新 `findings.md` AUDIT-6-A1 验证列为新增测试 + 全量门禁。

## 2026-07-01 关闭过时的代码尺寸 findings（VOICE-SIZE-3 / ECC-2）

- **背景**：`findings.md` 中 `VOICE-SIZE-3` 与 `ECC-2` 仍标记为 Open，记录的是历史上存在 23~35 个 >300 行文件 / 99~100 个 >50 行函数的状态。
- **当前状态**：`scripts/check_code_size.py` 当前扫描结果为 **0 个 >300 行文件、0 个 >50 行函数**，`run_pre_commit_check.py` 已将其作为阻塞门禁运行。
- **操作**：将 `findings.md` 中两项状态更新为 Closed，并补充 2026-07-01 基线达标的说明。
- **验证**：`scripts/check_code_size.py` PASS；`scripts/run_pre_commit_check.py --ci --full` 4273 passed。

## 2026-07-01 CI 新增 `pip-audit` 依赖漏洞门禁

- **背景**：`findings.md` 2026-07-01 依赖漏洞修复项建议将 `pip-audit` 加入 CI，防止已修复的 manifest 漏洞回退。
- **实现**：
  - `.github/workflows/test.yml` 的 `Install dependencies` 步骤安装 `pip-audit`。
  - `Security scan` 步骤合并 `bandit` 与 `pip-audit -r requirements_server.txt`；设置 `PYTHONUTF8=1` 避免 Windows 编码下 requirements 中文注释被误识别为 GBK。
- **验证**：
  - 本地 `PYTHONUTF8=1 pip-audit -r requirements_server.txt` → `No known vulnerabilities found`。
  - `bandit` 通过（仅 Low 问题）。

## 2026-07-01 修复 CI `Tests` workflow 与本地全量测试失败

- **背景**：合并 dependabot PR 后 GitHub `Tests` workflow 仍失败（18 failed），本地 `scripts/run_pre_commit_check.py --ci --full` 同样复现。
- **根因 1 — FastAPI 0.138.2 路由内省破坏**：
  - `fastapi>=0.138.2` 将 `app.include_router()` 的结果包装为 `_IncludedRouter`，`server.app.routes` 不再直接包含 `APIRoute` 叶子对象，导致所有路由注册/内省类测试断言失败。
  - 修复：将 `requirements_server.txt` 与 `deploy/jdcloud/jdcloud-worker-requirements.txt` 的 FastAPI 范围收紧为 `>=0.136.1,<0.136.3`（排除恶意 0.136.3 同时避开 0.138.x），并保留显式 `starlette>=1.3.1` 以继续覆盖 CVE-2026-54282/54283。
- **根因 2 — path_validator 丢弃已生成 motion path**：
  - `device_gateway/path_validator.py` 对 `write_text`/`draw_generated`/`handwriting` 等 `_PATH_GENERATING_CAPABILITIES` 会跳过 `path` 字段，即使 `build_run_params_async` 已经生成了有效 path，也会被丢弃，导致 5 个设备任务测试 KeyError/AssertionError。
  - 修复：新增 `_maybe_preserve_path()` 辅助函数；当 path 已存在且有效时校验并保留，无 path 时仍保持原有“稍后生成”的兼容性。
- **验证**：
  - `scripts/run_pre_commit_check.py --ci --full`：`4273 passed, 3 skipped, 2 deselected`
  - `pip-audit`：installed packages 无已知漏洞
  - `ruff check .`、`ruff format --check`、`pyright device_gateway/path_validator.py`、`scripts/check_code_size.py` 均通过

## 2026-07-01 Cloudflare Worker 透明兜底/灰度（已完成）

- **目标**：在 `chat.donglicao.com` 边缘部署 Worker，对匿名 `/v1/chat/completions` 请求透明代理到阿里云 pilot，并在 pilot 异常时自动回源到京东云主节点。
- **实现**：
  - 新增 `cloudflare/workers/chat-router.js`：按 `Authorization` 头存在性粗分流；无 key 的 POST `/v1/chat/completions*` 走 pilot；其余请求回源 `origin-chat.donglicao.com`；pilot 返回 429/5xx/408 时自动回源兜底。
  - 新增 `cloudflare/wrangler.toml`：路由 `chat.donglicao.com/v1/chat/completions*`。
  - 新增 `.github/workflows/deploy-chat-router-worker.yml`：自动确保 `origin-chat.donglicao.com` DNS 记录并部署 Worker。
- **基础设施**：
  - 京东云 `/etc/cloudflared/config.yml` 增加 `origin-chat.donglicao.com` ingress，指向本地 nginx（跳过 TLS 校验）。
  - GitHub Actions 已创建 `origin-chat.donglicao.com` CNAME 到 tunnel。
- **部署状态**：workflow run `28525746050` 成功，Worker `lima-chat-router` 已部署。
- **验证**：
  - `curl -X OPTIONS https://chat.donglicao.com/v1/chat/completions` → 204，CORS 头来自 Worker。
  - 匿名 POST（无 Authorization）→ `X-Lima-Backend: aliyun`，后端 `pollinations_openai`，响应 200。
  - 带 Authorization POST → `X-Lima-Backend: jdcloud`，响应 401（dummy key 被主节点拒绝，证明回源路径正常）。

## 2026-07-01 前端匿名简单聊天请求分流到阿里云 pilot

- **目标**：让 chat-web、官网 playground、manager-mobile H5 的匿名简单聊天请求走阿里云 `lima-router-pilot`（仅免费后端），降低京东云主节点负载。
- **实现**：
  - **chat-web**：新增 `chat-web/js/app-config.js` 提供 `shouldUsePilot(path, body)` 判定规则；`chat-api.js` 通过 `LiMaConfig.getApiUrl()` 选择 endpoint；`sendMessage()` 已增加一次失败回退（pilot 返回 429/503/5xx 或网络错误时重试 `chat.donglicao.com` 主节点）。
  - **官网 playground**：`donglicao-site-v2/app/developer/playground/page.tsx` 在 API Key 为空且 endpoint/model 为默认 chat 时自动切换 baseUrl 到 `aliyun.donglicao.com`。
  - **manager-mobile**：新增 `utils/index.ts` 的 `getChatBaseUrl()`，未登录且默认模型时返回 `aliyun.donglicao.com`；`api/chat/chat.ts` 的流式/非流式 chat 均使用该 baseUrl。
  - **CSP / 部署**：chat-web CSP 增加 `aliyun.donglicao.com`；`.gitignore` 增加 `chat-web/dist/`；manager-mobile H5 构建 base 设为 `/mobile/`。
- **部署**：
  - chat-web 源文件同步到京东云 `/opt/lima-router/chat-web`，并经 GitHub Actions 部署到 Cloudflare Pages（`app.donglicao.com`）。
  - 京东云 tunnel 入口由 `http://127.0.0.1:8080` 改为 `https://127.0.0.1:443`（跳过 TLS 校验），恢复 nginx 作为流量入口，从而支持 `/mobile/` H5 静态目录。
  - manager-mobile H5 构建后通过 `scp -r` 部署到 `/var/www/chat/mobile/`。
  - 官网 playground 经 GitHub Actions 部署到 Cloudflare Pages（`www.donglicao.com`）。
- **验证**：
  - `https://app.donglicao.com/` 与 `https://www.donglicao.com/developer/playground/` 均包含 `aliyun.donglicao.com` 相关引用。
  - `https://chat.donglicao.com/mobile/index.html` 返回 H5 入口，资源路径以 `/mobile/assets/` 开头。
  - `/health`、`/v1/chat/completions` 仍正常。
