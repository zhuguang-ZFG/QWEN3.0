# LiMa 系统瘦身设计文档

- **日期**: 2026-07-02
- **状态**: 已批准，执行中
- **触发**: 用户提出「小程序交互复杂化了，不能一键登录？」+「后端是不是过度设计」
- **范围**: 固件（U8/U1）、后端（Python）、文档、小程序 —— 全四维度
- **原则**: 先做减法，后做加法。YAGNI 优先于功能扩张。

---

## 一、核心结论

四维度量化审查结论：**过度设计系统性存在，但分布不均。** 三个反复出现的模式：

1. **为没走过的路建桥**（投机建设）—— 手机号+SMS 鉴权端点、U1 的 WebUI、6 个声码器驱动
2. **同一概念散落多处**（碎片化）—— `routing_engine` 拆 9 文件、绘图 UI 做 3 套、Ponytail 规则重复 6 份
3. **死代码舍不得删**（堆积）—— 98MB node_modules、352 行 DEPRECATED、121 文件 archive

**先做减法的理由**：在给一个已有过度设计倾向的系统再加新功能（如语音控制）之前，先清理基线，降低维护面和认知负担，避免新工作建立在错误前提上。

---

## 二、四维度量化证据

### 2.1 固件 🔴 最严重

| 证据 | 位置 | 量级 |
|------|------|------|
| U1 提交了 node_modules | `esp32S_XYZ/firmware/u1-grbl/embedded/node_modules` | **98 MB** |
| U1 编译进 WiFi/BT WebUI | `Grbl_Esp32/src/WebUI/` 26 文件 | **6,410 行** |
| U1 未用驱动常编译 | `Spindles/`(13) + `Motors/`(10) | 实际只用 PWM + StandardStepper |
| U8 音频协议自相矛盾 | `websocket_protocol.cc:233` 声明 PCM，`audio_service.cc:406` 永远 OPUS | **潜在 bug** |
| U8 死依赖 TMCStepper | `platformio.ini`；`dlc_motor_control_p1.h:19`「无 Trinamic UART」 | 死库 |
| U8 误导读 | `u8-xiaozhi/README.md` 宣传声纹/3D-Speaker | 代码零实现 |

正面：项目自有代码（`motion_executor.cc`、U8 协议处理、物理边界校验）很干净。过度设计全是继承的上游质量，没砍干净。

### 2.2 文档 🟠 数量级最大

| 证据 | 量级 |
|------|------|
| `progress.md` append-only 日志 | **11,580 行**，与 STATUS.md/findings.md 三处重复 |
| `docs/archive/` 堆放场 | **121 文件 / 38,380 行**，占 docs/ 文件数一半 |
| 8 个 agent 配置树并存 | ~9,300 行 agent 指令；Ponytail 重复 6 处，ECC 重复 4 处 |
| `.claude/skills/gitnexus/` | 6 个 SKILL.md 教用 GitNexus，AGENTS.md:294 明确禁止 —— 冲突 |
| 5 份重叠战略规划 | 3,255 行；V2 计划验收项未勾选、测试数（3730）对不上现状（4285）—— 遗弃 |
| STATUS.md 内部矛盾 | 1448 行「Telegram ✅已退役」vs 76-90 行当新功能 |
| 三个「权威」文档互相打架 | REQUEST_PIPELINE / DEPLOY_CONVENTION / AGENTS.md 都自称权威 |
| 断链引用 | AGENTS.md:254 `reference/ECC`、:319 `reference/ponytail/` —— **均不存在**（已核实） |

### 2.3 后端 🟡 概念碎片化，非臃肿

| 证据 | 量级 |
|------|------|
| 文件尺寸纪律 | 423 文件中**仅 1 个超 300 行** —— 纪律好 |
| `routing_engine` 拆 9 个根文件 | 1,009 行，读一个决策要开 14+ 文件 |
| `routing_executor` 拆 5 个、`intent` 概念散 4+1 | 概念碎片化 |
| 两个并行选型包 | `router_v3/`(484) + `routing_selector/`(454) + `route_scorer.py`(213) = 1,151 行散 3 处 |
| 352 行已声明废弃但仍编译 | `capability_matrix.py`(187) + `speculative_policy.py`(126) + `routes/eval_internal.py`(39) |
| Telegram 代码 216 行未标退役 | `integrations/telegram_bot/`（gallery 依赖，**已核实**） |
| 47 个文件含 `except:pass/continue` | 违反硬规则，含热路径 |
| 文档吹 2.5 倍 | AGENTS.md 说 context_pipeline「43 模块」，实际 17 |

### 2.4 小程序 🟢 不是最重

| 证据 | 量级 |
|------|------|
| 登录**本身就是一键登录** | `pages/v2/login/index.vue` `uni.login`→`v2Login`，无门禁 —— 直觉对，归因错 |
| 绘图/写字能力做 3 遍 | create.vue(937) + device-detail write-draw-panel + device-list quick-draw |
| 3 个首页重叠 | device-list / index(智能体=WorkshopHome) / mine |
| 3 个后端鉴权端点死代码 | `auth/register`、`auth/sms-verification`、`auth/captcha` 前端零引用 |
| settings 是 744 行杂物袋 | 6 语言含德/越/葡（臆测） |
| 4 个法律页 = 1,885 行 | privacy/agreement × zh/en |
| 「配网」是永久 tab | 一次性 onboarding 却占永久位 |

---

## 三、瘦身优先级清单（20 项）

### P0 —— 安全删除/修复（8 项，1.5 天）

| # | 项 | 动作 | 验证 |
|---|----|------|------|
| P0-1 | 删 U1 的 98MB node_modules | 移除 + .gitignore | 子模块体积降；platformio 仍编译 |
| P0-2 | U1 关 WiFi/BT 编译开关 | 默认 env 加 `-DDISABLE_WIFI` | 编译产物 < 原 70%；U1 仍响应 UART 命令 |
| P0-3 | 修 U8 音频协议矛盾 | 调研后端 ASR 实际格式，统一 hello 与 audio_service | 端到端语音冒烟 |
| P0-4 | ~~删 3 个 DEPRECATED 后端文件~~ → **修正为：修正矛盾标记** | 核查发现 `speculative_policy.py`/`capability_matrix.py` 标 DEPRECATED 但实际是热路径依赖（被 `speculative.py`/`complexity.py`/测试使用）。**不能删**。改为修正顶部注释，明确「coding 退役，模块本身未退役」。`eval_internal.py` 确为退役态（返回 410，测试依赖），保持原状 | grep 标记与实际一致；pytest 全绿 |
| P0-5 | Telegram 标退役（gallery 依赖，不删） | 标 `# DEPRECATED`；AGENTS.md 注明 gallery 待迁移 | grep 梳理调用链 |
| P0-6 | 修 AGENTS.md 3 处断链 | reference/ECC→.claude/ecc；reference/ponytail/ 删段或改 | grep 引用全可达 |
| P0-7 | 修 STATUS.md Telegram 矛盾 | 1448 行改为「bot 通知退役，gallery 存储复用 TG Bot API」 | STATUS 自洽 |
| P0-8 | 删 `.claude/skills/gitnexus/` | 删 6 个子 skill | find 无 gitnexus skill 残留 |

### P1 —— 低风险整理（7 项，2 天）

| # | 项 | 动作 |
|---|----|------|
| P1-9 | 合并 5 份战略文档归档 | 未完成项并入本文档；原文档 git mv 到 `docs/archive/strategic-plans-2026-06/` |
| P1-10 | 截断 progress.md | 保留近 30 天；历史 git mv 到 archive；顶部加索引 |
| P1-11 | 清理 docs/archive/ | retired/*.py 移出 docs 树；加 README 说明规则 |
| P1-12 | 合并 8 agent 配置树 | 以 AGENTS.md 为单一源；重复规则改指针 |
| P1-13 | routing_engine 9 文件归包 | 新建 `routing_engine/` 包，移入，保 facade |
| P1-14 | routing_executor 5 文件归包 | 新建 `routing_executor/` 包 |
| P1-15 | 修 AGENTS.md 模块数 | 「43 模块」→ 实际 17 |

### P2 —— 中风险重构（5 项，3.5 天，必须 TDD）

| # | 项 | 动作 |
|---|----|------|
| P2-16 | 删小程序 3 个死鉴权端点 | 删 register/sms-verification/captcha 路由+逻辑 |
| P2-17 | 合并 create.vue 嵌套 tab | 统一到 device-detail 2 步流 |
| P2-18 | 合并 3 个首页 | tabbar 5→3-4 |
| P2-19 | settings 瘦身 | 语言裁到 zh_CN+en；拆分杂物段 |
| P2-20 | 审查 47 个 except:pass | 逐一补 logger.warning 或记 PONYTAIL-DEBT |

---

## 四、执行顺序

- **第 1 周**：P0 全部 → P1 文档去重(9-11,15) → P1 agent 树(12)
- **第 2 周**：P1 后端包归拢(13,14) → P2 删死端点(16) → P2 settings(19)
- **第 3 周**：P2 UI 合并(17,18) → P2 异常审查(20)

每项独立 commit 可回滚；P2 必须 TDD；每个 P 级完成后更新 STATUS/progress/findings。

---

## 五、不做的事（YAGNI 边界）

- ❌ 不重写 routing pipeline（13 步有文档、单职责、不超限 —— 合理设计）
- ❌ 不动 backends_registry（170+ 后端必要规模）
- ❌ 不全删 archive（只做结构整理）
- ❌ 不在本文档加新功能（语音控制等留待瘦身后另起 spec）

---

## 六、风险与回滚

| 风险 | 缓解 |
|------|------|
| 删 DEPRECATED 有隐藏依赖 | 删前 `codegraph impact` + grep；保留 commit 可回滚 |
| U1 关 WiFi 后 OTA/调试失效 | 保留源文件只改编译开关；需要时单 env 重开 |
| 小程序 UI 合并破坏习惯 | P2-17/18 前与用户确认；保留旧页面一个版本期 |
| 文档归档后找不到历史 | archive/ 加 README 索引；progress 顶部留指针 |

通用回滚：每项独立 commit，`git revert <sha>` 即可。

---

## 七、验收标准

**P0 完成**：node_modules 不存在；U1 编译产物 < 原 70%；U8 音频协议一致；后端无 DEPRECATED 残留；AGENTS.md 引用全可达；STATUS 无矛盾；无 gitnexus skill。

**P1 完成**：docs/ 根战略文档 ≤ 2 份；progress.md < 500 行；Ponytail 命中点 ≤ 2；routing_engine/executor 各自为包；模块数与实际一致。

**P2 完成**：后端无 register/sms/captcha 路由；绘图/写字 ≤ 3 步；tabbar ≤ 4；settings < 400 行；47 个 except:pass 审查完毕。

---

## 八、与现有文档的关系

- **本文档取代**：5 份战略规划文档中重叠的诊断/改进部分（P1-9 执行后归档）
- **本文档不取代**：STATUS.md、findings.md、AGENTS.md、REQUEST_PIPELINE_AUTHORITY_CN.md
- **后续**：瘦身后若启动语音控制等功能，另起 spec，引用本文档作为「基线已清理」前提
