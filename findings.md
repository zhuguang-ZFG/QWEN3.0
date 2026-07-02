# LiMa Findings

> 历史归档：2026-06 及更早非审计条目 → [`docs/archive/findings-2026-06-CN.md`](docs/archive/findings-2026-06-CN.md)
> AUDIT 审计批次：2026-06-28/29 AUDIT-1~12 → [`docs/archive/findings-2026-06-audit-CN.md`](docs/archive/findings-2026-06-audit-CN.md)

## 2026-07-03 深度瘦身 K2+L+M+N 合批结项：F401 全局门禁启用 + 闭环 + CI 同步

- **K2 教训 (e) 型态「fixture 间接依赖链」新发现**：G1b 记录的 F401 失败四型态 (a)(b)(c)(d) 之外，本批又发现第 (e) 型态 —— 「pytest fixture 间接依赖 fixture 链」。`import fake_u1` 在测试函数签名 (`test_xxx(lima_client, fake_device_server)`) 没出现，但 helper 模块下 `@pytest.fixture\ndef fake_device_server(fake_u1: dict)` 依赖 `fake_u1` 作为 fixture 参数；pytest 收集 test 时通过 fixture 依赖图 resolve `fake_device_server` 又递归 resolve 它的 `fake_u1` 参数，需要 `fake_u1` 名字在 helper 模块的 namespace 里可见，而 import 就是为了让 helper 模块加载到 sys.modules 完成 fixture 注册。删了立即 `fixture 'fake_u1' not found`。修复：尽管理论上 import 不必保留（pytest 应自行发现 fixture），实证删 import 即错——保留 import + `# noqa: F401  pytest fixture, transitively required` 注释释明。
- **L 批 grep-误报 lesson**：ruff F401 报告里附带的 dashed-name bare token 用 `\b...\b` grep 验证会命中**字符串字面量 / 注释 / 函数名** —— `pytest` 命中 `"pytest"` 字符串比较 `"pytest"`、`json` 命中 httpx keyword `json={...}`、`asyncio` 命中 `@pytest.mark.asyncio` 装饰器名（**那不是 asyncio 模块用法**）、`http.client` 命中 docstring "WebSocket client"、`sys` 命中 `via sys.modules` 注释。本批 audit 脚本 grep 显示 6 risky 实际全可删。教训：grep `\bNAME\b` 作为 F401 真死判断不够，需配合上下文人工识别（字符串字面量 vs 真模块用法），但配合 ruff --fix 的 pure 删除模式（ruff 不删 active import），可大胆 `ruff --fix` 后立即 pytest 验证。
- **M 批生产侧 exclude reference lesson**：reference/grbl_fix/ 5 个 F401 在 `sys.state` 等 C++ 代码字符串字面量里被 ruff 识为活，但 module sys 真死。决策按 AGENTS.md「禁止暂存参考仓库」改为在 `ruff.toml` `exclude = ["reference/**"]` 直接豁免，不删 F401。这与生产路径 F401 gate 启用后不冲突——exclude 的目录 ruff 完全不扫，对主线行为产线零影响。
- **M 批 ruff format 副作用 lesson**：`ruff --fix --select F401 .` 不会改 format，但本批紧跟的 `ruff format .` 一并规范化了 23 个生产 / tests 文件（EOL 缺尾 newline / 单→双空行 / Optional[X]→X|None 等 G1b 后周期早应做过的格式化）。这些 silent 升级 G1b 时是否有意保留 NO，本批一并打平。教训：每次格式化 repo-wide 各种 small NIT 改动，应单独 commit 或明确记录到 progress，避免 noise 混进 F401 逻辑批的 commit。本批遵守「K2+L+M+N 合一 commit」原则一次过。
- **里程碑意义**：F401 全局 gate 启用 = 从 G1b 提出的「四型态具名失效 + lesson learned」到现在的工程闭环。今后 TDD 抽离批次会有 ruff 全 repo F401 0 报告做 baseline 守护，新的死 import 引入会立即被本地 commit + CI 双门拒收，不再有 F401 静默死代码潜逃空间。H2 的 F401 安全门 (`pytest --collect-only`) 与 M 的 ruff F401 全局 gate 形成两层防线 —— ruff 第一道静态过滤，pytest 收集动态验证字符串匹配/fixture 间接依赖 (d)/(e) 型态。

## 2026-07-03 深度瘦身 K 批次结项：测试侧 mixed 桶 10 文件 39 个真死 imported-name 逐文件清理

- **K 批次审计 agent 不可全信 lesson**：本批再次证明「依靠 Explore/general-purpose agent 给出的 F401 归桶分类绝不可直接作为删除依据」。审计 agent 在 mixed / domain dead 两桶里把 `fake_device_server`/`fake_u1`/`lima_client`/`accept_share`/`client`/`seed_guest` 归为「domain dead imports 可删」—— 但这 6 名都是 G1b 已显式记录的 (d) 「pytest fixture 字符串匹配注入」型态（在测试函数签名作为参数名出现、pytest 收集期注入、ruff 看不见），删了会再现 18 ERROR。**教训**：F401 批量清理的 grader 必须是「亲自 Read + ripgrep 含 `@pytest`/`pytest.`/fixture 名/builtin 装饰器等多重 grep」人工审视，agent 报告只能作为初始引导而非最终删除清单。本批用此方法把 plan 锁定的 37 个删名扩展到 39 个（补了 `os` 与 `verifier as attestation_verifier` 两个我之前 Read 时漏审的真死名）。
- **K 批次 monkeypatch.setattr 字符串属性 ≠ import 别名 lesson**：`test_device_attestation.py` 中 `attestation_verifier` 字符串出现在 `monkeypatch.setattr(handlers, "attestation_verifier", ...)` 多处，第一反应会认为 import 别名 `verifier as attestation_verifier` 是必需的；实际 `setattr` 的第二参数只是属性名字符串，handlers 自己有 `attestation_verifier` 属性，本文件 import 的别名并不被引用，删安全。这种「import 别名 = 已存在 attribute 名」的字符串字面量引用是另一种 F401 隐蔽活跃假象。
- **K 批次新形态「局部变量遮蔽 import」lesson**：`test_provider_automation_model_entry.py` 中 `from provider_automation_helpers import entry` module 与文件内每个测试函数的 `entry = ProviderModelEntry(...)` 局部变量同名，所有 `entry.xxx` 都用局部实例、永远不引用 module import。这意味着 module import 真死可删，但需 visualize 全文件每个 `entry` 出现位置的上下文（`entry = ProviderModelEntry(...)` 分配行 vs `entry.xxx` 使用行）才能区分二者。ruff 默认把 import `entry` 视为活（因为名字 `entry` 在文件中出现），实际是遮蔽假活 —— ruff 此处表现尚算正确报了 F401，但人工审视要小心局部变量同名遮蔽带来的视觉混淆。
- **K 批次不动 6 文件 (d) 注入型态说明**：fake_u1_cloud 4 文件 (`test_fake_u1_cloud_draw_svg.py` / `home` / `rejection` / `write_text`) 与 device_app_sharing 2 文件 (`test_device_app_sharing.py` / `_permissions.py`) 的 `fake_device_server`/`fake_u1`/`lima_client`/`accept_share`/`client`/`seed_guest` 在测试函数签名参数出现，属 (d) pytest fixture 注入型态。这两类真正永久解法：(a) 在 helper 模块 (`fake_u1_helpers.py` / `device_app_sharing_helpers.py`) 的 `# noqa: F401` 上注明 re-export/fixture 用途；(b) 在消费测试文件直接 `# noqa: F401` 后跟 `# fixture injected by pytest` 释明。本批暂留 K2 批处理。
- **K 批次效果**：测试侧 F401 总数从 141 减到 102（删 39）；含 F401 文件数从 91 减到 81（删文件内全部 F401 的进入 0 报告状态）。门禁全程绿，无运行时行为变化。

## 2026-07-03 深度瘦身 J 批次结项：唤醒词握手层抽离到 accept_websocket_upgrade 纯函数

- **J 批次 accept_websocket_upgrade 接缝设计结论**：抽离不另起新模块（Ponytail YAGNI：能不拆就不拆）——握手协议就放在 http_server.py 顶部模块层级，与 `build_handler_class` 工厂并列；接受 duck-typed `handler` 参数注入 `.headers.get / .send_response / .send_header / .end_headers / .send_error / .connection / .wfile` 七个实例 API，返回 `(reader, writer)` 或 `None`（已 send_error 后）。**关键设计点**：_RDONLY 直引 `SimpleHTTPRequestHandler` 类型注解就够（不需要顶层属性 + lazy `_resolve_*()` 兜底链模式，因为 handler 是从类外部注入而不是要在 importlib 无父包环境里相对导入），相比 `websocket_session / bridge_request_handler` 的 callback 注入模式更简单。`_handle_websocket` 从 >20 行收紧到 ~9 行接缝（`upgraded = accept_websocket_upgrade(self)` → `None 则 return` → `reader, writer = upgraded` → `serve_websocket_session(...)`）。
- **J 批次契约特征化测试 lesson learned**：I 批次 plan 在候选清单里提到「Sec-WebSocket-Version 不校验」是潜在改进点，本批 TDD RED-first 把它显式化为特征化测试 `test_websocket_handshake_succeeds_without_sec_websocket_version`——用 `ws_handshake(include_version=False)` 触发握手，断言还能 101 + 收到 bridge_connected ready frame。**教训**：纯结构重构步骤里若有「未来可改进 X」的契约盲点，先把现状显式写成特征化测试，是把隐性契约转成显式契约、避免将来悄悄收紧校验时 silent break 浏览器/客户端的最廉价手段。本测试若将来引入 Version 13 严校验会变红，由改 PR 显式决策契约方向，而非静默回归。
- **J 批次进度同 I 批次一致**：full 4427 → 4428 passed（恰好 +1）、check_code_size PASS、ruff + pyright 全过、http_server.py 170 → 187 行（结构 +17 行新函数 / -9 行 _handle_websocket，净 +1 行，远低于 300 限）。

## 2026-07-03 深度瘦身 I 批次结项：唤醒词 http_server 类工厂抽离 + 握手错误路径特征化测试

- **I 批次死代码诊断结论**：F2 抽离 `frame_codec`、G2 抽离 `bridge_request_handler`、H1 抽离 `websocket_session` 后，`data/digital-human/wakeword_runtime/runtime/http_server.py` 的 `_build_server` 内嵌 `TestRuntimeHandler` 类残留 **7 个一行 delegator wrapper 方法**（`_build_wakeword_config_message` / `_handle_bridge_request` / `_save_wakeword_config` / `_receive_websocket_message` / `_read_exact` / `_send_websocket_text` / `_send_websocket_frame`），方法体都只是 `return <已抽离模块的顶层函数>(...)`，但因 `_handle_websocket` 改成直接调 `websocket_session.serve_websocket_session(...) / bridge_request_handler.handle_bridge_request(...)` 等顶层函数，**全仓 ripgrep `self._<method>` 0 命中**，确认是纯死代码。**教训**：每一次「抽离纯函数模块 + 把调用点委托到顶层」的重构收尾必须 grep `self._<method>` 审计遗留 delegator，否则会静默残留无消费者的一行包装直至下次人工巡察——本批 7 个 wrapper 累积已 ~6 月（跨越 F2/G2/H1 三批，每批抽离后未立即清 delegator，全部留到本批一次性销账）。**改进**：未来抽离批次步骤应固化「5 解析调用点 → 6 调用点委托到顶层函数 → 7 grep `self._<原wrapper>` 删 delegator」三步成链条。
- **I 批次类工厂抽离结论**：原 `_build_server` 把 `class TestRuntimeHandler(SimpleHTTPRequestHandler)` 嵌在闭包体内只捕获 `test_root / event_bridge / schedule_restart` 三个自由变量。抽到模块级 `build_handler_class(test_root, event_bridge, schedule_restart) -> type[SimpleHTTPRequestHandler]` 后——(1) 与三个姐妹模块（`frame_codec` / `bridge_request_handler` / `websocket_session`）「模块级纯函数」风格对齐，handler 类也可在 `http_server.build_handler_class(...)` 直接构造/单测而无需实例化 `TestRuntimeHttpServer`；(2) `_build_server` 收缩到 4 行「调工厂 + ThreadingHTTPServer + daemon_threads + return」；(3) 闭包捕获不变（仍是同 3 个 deps），无新运行时行为，纯结构重构。**保留不抽的部分**：`_handle_websocket` 握手路径仍强依赖 `self.headers / self.send_response / self.send_error / self.wfile / self.connection`，本轮不动；并在模块顶部 ponytail docstring 标注上限「握手层强依赖 SimpleHTTPRequestHandler 实例 API」+ 升级路径「换 wsproto/starlette 框架后将握手层一并下沉」。
- **I 批次握手错误路径特征化测试结论**：H1 端到端集测只覆盖 happy-path 101 握手（通过 support helper `ws_handshake` 的隐式 `"101" in status_line` + `Sec-WebSocket-Accept` 校验），**两 BAD_REQUEST 分支（无 Upgrade 头、无 Sec-WebSocket-Key 头）此前零覆盖**。本批以特征化测试（非新功能、锁现有契约）补 2 个 http.client 测试，跑过即绿，使下一步类工厂抽离有完整回归网。**意义**：TDD 在纯结构重构场景下「先 RED 不可能、改用特征化测试锁现有契约」是正确变体——这是 TDD-not-an-ideology 的可证实用法。
- **I 批次 from-import 收敛结论**：删 7 个 wrapper 后唯一引用 `read_exact` / `send_frame` 的代码消失，把 `from .frame_codec import compute_accept, read_exact, receive_message, send_frame, send_text` 收敛到 `from .frame_codec import compute_accept, receive_message, send_text`（3 个），减小模块接口表面积、消除 F401 风险。

## 2026-07-03 深度瘦身 H1+H2 批次结项：测试侧 F401 安全门工具化 + 唤醒词 WebSocket 会话抽离

- **H2 F401 安全门工具化结论**：基于 G1b lesson learned（四类具名失效型态，特别是 pytest fixture 字符串匹配 (d) 类对 ruff 完全不可见）建仓化安全门：新建 `scripts/testside_f401_safety_gate.py`——本门在 pre-commit 流程中当且仅当 staged 文件含 `tests/*.py` 时触发 `python -m pytest --collect-only -q`，若收集失败（含 ERROR 等级）按 ERROR 行解析出失败测试文件，跳过 baseline-skip 文件后打印失败列表 + 四型态提示 + 收集尾 30 行 triage 输出，返回非零阻止提交。**设计要点**：(1) 触发型态判定用「file path 是否在 tests/ 子树」简单前缀，不依赖 git staged 列表的 pandas 化；(2) `--baseline-skip-from` 接受已知破损文件清单（不与 stdin 冲突），让渐进清理批可豁免旧债；(3) main() 函数经 `_build_argparser()` + `_print_blocked()` 拆分保持每个函数 ≤50 行通过 check_code_size；(4) 集成入 `run_pre_commit_check.py` 的 `run_testside_f401_safety_gate()`，置于其他快速检查之后、`--full` pytest 之前，保证 fixture-removal 类失败被快速捕获而非慢跑后才察觉。10 个 gate 单测验证纯 helper 行为（path 过滤、ERROR 解析、baseline 过滤、main 早早返回路径），不调用 pytest 本身避免依赖。**意义**：把 G1b 的「人工 lesson learned」永久固化为门禁，使下一批测试侧 F401 清理工作时即便是不同执行人，也能在误删 fixture 时直接被本地 commit 拒收，不再依赖运行时 pytest 才发现 18 errors 类型的灾难。
- **H1 wakeword WebSocket 会话抽离结论（了结 G2 「`_handle_websocket` 仍需先补端到端测试」遗留）**：以 TDD 方式补 `tests/test_wakeword_session_integration.py`（5 个端到端集成测试）：用 importlib + sys.modules alias package（`wakeword_runtime_pkg.{runtime,bridge}` 合成包）让 hyphen 路径 `data/digital-human/...` 可导入；fixture 在 ephemeral port 0 起 TestRuntimeHttpServer + 内嵌 plumbing（seed config.json/models/keywords.txt），测试驱动 raw socket + http.client + 手写 RFC6455 client handshake 跑 `/health`、握手 Ready 帧、`set_wakeword_config` round-trip、restart、unknown type fallback 五例。`pytest.importorskip("pypinyin")` 跳过外部依赖缺失环境以保证集测可跑。集成测试通过后（守住现有行为），抽 `_handle_websocket` 内嵌 46 行事件循环体（post-handshake 的 client_queue.add → greeting → 双向轮询 → finally remove）到 `websocket_session.py`（99 行纯函数模块 `serve_websocket_session(reader, writer, bridge, test_root, schedule_restart, send_text_writer, receive_reader_writer)`），http_server 仅保留 HTTP/WebSocket 握手（强 self.send_response/headers 依赖），178→164。沿用 frame_codec/bridge_request_handler 模式：`handle_bridge_request` 与 `build_wakeword_config_message` 顶层属性（非 from-import）链入由 http_server.py import 后 setattr 真实实现；测试可 setattr 注入 fake。集成测试在抽离前后全过，证明运行时行为不变。**关键 lesson learned 沉淀**：导入 plumbing（cosmetic alias package 注册 + http_server 加载 + WS frame helpers 计 130+ 行）必须在独立 `_wakeword_integration_support.py`（pytest 不收集因 `_` 前缀），保持 test 主文件 193 行 / support 191 行双双 ≤300；并验证 check_code_size 不漏判 scripts/testside_f401_safety_gate.py（73 行 main 函数拆 helper 通过 50 限）—— 两起台护在 H1+H2 落地中 ÷ 落林 met 限制反弹。
- **门禁全程绿**：`ruff check .` / `ruff format --check` clean（仅格式化本批新增/修改的 4 个 production G2/H1 文件 + 6 个 H2 测试/脚本文件）；`scripts/check_code_size.py` PASS（0 文件 >300、0 函数 >50，需拆 `_print_blocked` 与 `_build_argparser` 后通过）；`pyright` 本批 4 个相关文件 0 errors 0 warnings；全量 `pytest --tb=short -q` → **4425 passed / 3 skipped / 2 deselected / 0 failed**（较 G1+G2 的 4410 +15，与 H2 +10 gate 单测 + H1 +5 集成测试 一致）。pypinyin==0.55.0 已 pin 入 `.venv310` 测试环境（与 `data/digital-human/wakeword_runtime/requirements.txt` 一致）使 H1 集成测试可正常运行。

## 2026-07-03 深度瘦身 G1+G2 批次结项：台账销账 + 测试侧 F401 精选 + 唤醒词桥接请求抽离

- **G1a PONYTAIL-DEBT 台账销账结论**：`check_code_size.py 残留 12 个 51-54 行函数`条目经独立 AST 扫描（51-55 行范围、全仓非排除目录）确认实际已 **0 个超限函数**（E6-E9 等早批已清理），条目陈旧。删除条目并补「已结清」记录，无代码改动。**教训**：PONYTAIL-DEBT 触发条件「触发下一个生产函数超 50 行时一并清理」始终未触发，但债务实际已被前批隐式清偿，台账与代码事实脱节 6 个月以上。台账需周期性自检（如 CI 阶段对每个「当前标记」条目跑一次 AST 验证），不能只等触发条件。
- **G1b 测试侧 F401 精选清理结论**：测试侧 F401 共 202 处，分两群：(1) port-target / 隐式 fixture 用法（`pytest`/`os`/`time`/`unittest.mock.{MagicMock,AsyncMock,patch}`/`asyncio`/`importlib`/`builtins`/`threading` 共 ~80，多为 ruff 看不到的间接使用）—— 保留；(2) domain dead imports（`device_voice.exceptions.{AuthenticationError,ConfigurationError,VoiceProviderError}`、`device_gateway.attestation.*`、`client_keys.models.ClientKey`、`chat_models.{ChatRequest,Message}` 等 ~120，可安全删）。本批采用 STYPE 分类清理：49 个 STYPE_CLEAN 文件（safe-only）经 F1 别名感知审计全过 0 danger，逐文件 `ruff --fix` 移除共 84 处。剩 143 处为 KEEP-infra + mixed 文件留待后续批逐文件人工核对。
- **G1b 二轮 + 三轮审计盲点 + 修复**：F1 提炼的「别名访问」具名失效风险再加上 pytest 用 conftest 把 `tests/` 加到 sys.path，消费者写 `from fake_u1_helpers import ...`（**前缀基名**而非 dotted path `tests.fake_u1_helpers`）。审计脚本的 `module == file_dotted_path` 严格相等漏掉此模式，`tests/fake_u1_helpers.py` 经 `--fix` 误删 `motion_task_to_u1_commands` 后下游 `test_fake_u1_protocol_translation.py` 收集失败。**修复**：恢复 import 附 `# noqa: E402,F401`，说明 re-export。
- **三轮审计盲点（pytest fixture 字符串匹配）+ 修复**：恢复后仍 18 ERROR：`test_device_app_sharing.py`/`test_device_app_sharing_permissions.py` 用 `accept_share`/`client`/`seed_guest` 作 pytest fixture（在测试函数签名声明为参数），`test_fake_u1_cloud_*.py` 4 文件用 `fake_device_server`/`fake_u1`/`lima_client` 作 fixture。pytest 在**收集期**通过参数名字符串匹配发现 fixture，**对静态分析完全不可见** —— ruff 看不出这些 import 是 fixture 注入而非死导入。我的 INFRA_KEEP 列表只覆盖 `pytest`/`patch` 等内建 fixture，未覆盖测试模块自定义 fixture。修复：回退 6 个消费测试文件到 HEAD。**关键教训**：测试侧 F401 具名失效有四种型态 —— (a) `from <module_dotted> import <name>` 直引；(b) 模块别名访问 `<alias>.<name>`；(c) pytest sys.path 根基名引用 `from <baseline> import <name>`；**(d) pytest fixture 字符串匹配注入**（import 名作为测试函数参数名，由 pytest 收集期发现，ruff 完全不可见）。统一经验：**「批量 F401 清理安全门 = 删除前先 `pytest --collect-only` 通过全测试套件」**，而非单靠静态审计；或在 INFRA_KEEP 列表里把所有 `@pytest.fixture` 注解函数名 + 所有测试函数签名参数名全部动态加入 KEEP 集合。
- **G2 唤醒词桥接请求 handler 抽离结论**：F2 抽离 WebSocket 帧编解码后，http_server.py 嵌套类内剩余 44 行 `_handle_bridge_request`（捕获 `test_root`/`schedule_restart` 闭包，结构清晰）是合适的下一抽离粒度。以 TDD 方式补 6 个 RED 测试（importlib 加载、含 fake save_wakeword_config 注入验证 publish/build_message 契约、save 异常降级路径、restart 调度、unknown/empty 类型 fallback），新建 `bridge_request_handler.py`（121 行纯函数模块，`handle_bridge_request` 主入口 + 2 个 helper）。**关键解耦**：`save_wakeword_config` 不在顶层 from-import（避 importlib 无父包相对导入失败），改为顶层 `save_wakeword_config: Any = None` + `_resolve_save()` 延迟相对导入兜底；http_server.py 在 import 后 `bridge_request_handler.save_wakeword_config = save_wakeword_config` 显式链入真实实现，测试用 `setattr` 注入 fake。`WakewordEventBridge` 类型注解改 `Any`（duck-typed 避开 F821）。http_server.py 213→178 行，闭包依赖与 `_handle_websocket` 事件循环不动。**遗留**：`_handle_websocket`（46 行，与 `client_queue` 紧耦合）仍需先补端到端 WebSocket 集成测试再考虑抽离。
- **门禁全程绿**：`ruff check .` / `ruff format --check` clean（仅格式化本批改动的 4 个 G2 文件 + 7 个 G1b 测试文件因 `--fix` 后 ruff format 建议合并括号）；`scripts/check_code_size.py` PASS（0 文件 >300、0 函数 >50）；`pyright` 本批 3 个相关文件 0 errors 0 warnings；全量 `pytest --tb=short -q` → **4410 passed / 3 skipped / 2 deselected / 0 failed**（较 F1+F2 的 4404 +6 = G2 新增 6 个 bridge_request 测试）。

## 2026-07-03 深度瘦身 F1+F2 批次结项：死导入清理 + 唤醒词 WebSocket 帧编解码抽离

- **F1 生产路径 F401 死导入清理（精选策略）结论**：`ruff --select F401` 全库 341 处分布无序，但测试侧 ~253 处多为 patch-target 导入（曾导致 85 个收集错误），本批**只动生产侧**。采用「AST 审计 + 别名感知 + noqa 保留 re-export」两轮策略：第一轮扫测试 `from <module> import <name>` 与点号 `<module>.<name>`，识别 9 个 must-keep re-export，标 `# noqa: F401` 后逐文件 `ruff --fix`；首轮跑 pytest 出现 12 failed / 22 errors，根因是 server_bootstrap.MODEL_ID（被 server.py 生产侧 `from server_bootstrap import MODEL_ID` 重新引用）等 re-export 实际经**模块别名访问**（`dg._reset_for_tests()`、`_a.BACKENDS`、`hs.flush_pending_save()`、`text_to_path.list_handwriting_fonts()`），第一轮纯文本扫描漏检。第二轮「别名绑定 → 别名点号访问」双向解析审计覆盖全仓未改文件，补出 9 个 must-keep，全用 noqa 恢复后门禁转绿。**关键教训**：模块别名（`import M.sub as A` / `from pkg import sub`）会把 re-export 使用方从源模块全名变成短别名，单测「import 一次 = 可被 patch」不是高危机型态；「re-export 被下游模块别名访问」才是更高危且更隐蔽型态。安全审计必须同桌双向解析。统计：清理 ~97 处（91 真死导入 + 17 noqa 保留 re-export，少数原有重叠）。剩余测试侧 F401 ~253 处留待后续单独批逐文件人工核对。
- **F2 唤醒词 WebSocket 帧编解码抽离结论**：E8 批次曾保守地把自我/socket 依赖的 WebSocket 帧实现留在内嵌 handler 中（无测覆盖、不敢盲拆）。本次以 TDD 方式补齐：先全 16 个 RED 测试（`tests/test_wakeword_frame_codec.py`，用 importlib.spec_from_file_location 加载避开 hyphen 路径不可直接 import 问题，覆盖 compute_accept RFC6455 范例向量、read_exact 短 EOF、receive_message masked/unmasked 解掩码/ping 自动 pong/close 抛 ConnectionAbortedError/pong 忽略/未知 opcode/126 扩展长度/空载荷、send_frame <126/126/127 三种长度编码、round-trip），再新建 `data/digital-human/wakeword_runtime/runtime/frame_codec.py`（118 行纯 stdlib 函数模块包含 compute_accept/read_exact/receive_message/send_frame/send_text 五个纯函数，模块头附 ponytail 注释说明上限「仅 RFC6455 最小帧子集，无分片/RSV」与升级路径「换用 wsproto」），最后 REFACTOR http_server.py 委托：`_handle_websocket` accept 计算、`_receive_websocket_message`、`_read_exact`、`_send_websocket_text`、`_send_websocket_frame` 全部委托 frame_codec。**闭包依赖 `test_root`/`event_bridge`/`schedule_restart` 与 `_handle_websocket` 事件循环主逻辑不动**，仅 codec 抽离；WebSocket 帧读写仍由 `self.connection`（reader）/`self.wfile`（writer）传递，运行时行为不变。http_server 274→212，新模块 118 行附 ponytail: 标记。**正式了结 E8 遗留**「WebSocket 帧实现仍为内嵌 284 行函数，未来需补测后再考虑拆分」。
- **F3 test_jdcloud_push_probe.py 贴顶下移结论**：300 行贴顶的测试文件尝试提取 `monkeypatch_post` shared-feature 合并 3 处 `monkeypatch.setattr(push_probe_results, "_post_payload", ...)`：实测反而增至 305 行（fixture 定义净增 11 行，仅每个 test 删 3 行），未达瘦身目标，**回退**保持 300 行现状（贴顶但未破门禁，符合 ≤300 限额）。下次若需进一步降行，需用更紧凑 fixture + 函数尾部断言合并，或重排测试以合并相似前缀，但收益微小，优先级低。
- **门禁全程绿**：`ruff check .` clean；`ruff format --check` clean（仅格式化本批改动的 4 个 routes/router_v3 文件，未触碰既有 10 个 pre-existing format-dirty 文件以避免污染 diff）；`scripts/check_code_size.py` PASS（0 文件 >300、0 函数 >50）；`pyright` 对本批改动的 8 个生产文件 0 errors（仅 `routes/device_gateway.py` 2 个与 F1 无关的既有 JSONResponse.get 误警，与 HEAD 相同）；全量 `pytest --tb=short -q` → **4404 passed / 3 skipped / 2 deselected / 0 failed**（较 E6-E9 的 4388 +16，与 F2 新增 16 个 frame codec 测试一致）。

## 2026-07-02 深度瘦身 E6-E9 批次结项：长函数/退役端点/唤醒词抽离/台账同步

- **E7 eval_internal 退役端点移除结论**：`routes/eval_internal.py` 自 v3.0 起为 410 Gone 桩（`/internal/v1/eval/call`，原用于 FRP 本地代理直连后端评估，编码能力退役后保留作占位）。经全库 grep 核实，生产代码与测试中仅路由注册 + 退役测试两处引用，**无任何运行时调用方**。确认安全删除：文件删除 + `route_registry.py` 注册行移除 + `test_eval_internal_is_retired` 测试移除。删除后 `route_registry` import OK，23 个 routing authority 测试全过（删除前 23→删除后 22，与移除单测一致）。
- **E8 唤醒词运行时抽离结论**：`data/digital-human/wakeword_runtime/runtime/http_server.py` 是独立运行的唤醒词本地 HTTP 服务（含内嵌 `TestRuntimeHandler` + WebSocket 帧实现）。该文件位于 `data/` 目录（被 `check_code_size.py` 排除审计）且**无任何测试覆盖**。本次仅抽离「无 socket/self 依赖的纯逻辑」（配置读/写/拼音转换）到 `wakeword_config.py`，保留强依赖 `self.connection` 的 WebSocket 帧逻辑在内嵌 handler 中以免破坏未经测试的闭包语义。http_server 347→274，新模块 96 行并附 `ponytail:` 标记记录 pypinyin 依赖上限。**遗留**：WebSocket 帧实现仍为内嵌 284 行函数，未来需补测后再考虑拆分。
- **E9 PONYTAIL-DEBT 台账同步结论**：核对源码后发现台账中 6 条标记对应代码已物理移除（capability_matrix/task_creation/task_events/mqtt_client/quota 的 lazy-import 解耦已落地、chat-web config.js 文件已不存），属「已结清但台账未销账」的脱节。同步删除 6 条失效条目、修正 3 条偏移行号、补录 1 条新标记。**教训**：台账应与每次解耦落地同步销账，否则会累积失真。
- **门禁**：ruff/format clean；pyright 0 errors（pypinyin 可选依赖 warning 与抽离前一致）；check_code_size PASS；全量 pytest **4388 passed / 3 skipped / 2 deselected**（exit 0，149.56s）。
- **下一步**：commit/push origin → VPS 部署 + 公网冒烟。

## 2026-07-02 系统瘦身 P2-17/18/19/20 + 参考改善 T1/T2 全部闭环

- **范围**：P2-17/18（UI 合并）、P2-19（settings 瘦身）、P2-20（except:pass 审查）+ T1-1（语义分类器）、T1-2（管道架构）、T1-3（Hershey 字体）、T2-2（健康探针）、T2-3（任务时间线）、T2-1（FluidNC 迁移准备）
- **P2-20 发现**：83 处 `except:pass/continue` 中仅 3 处是真正的宽泛异常静默吞掉（违反硬规则 #1），其余 80 处是特定异常类型（`json.JSONDecodeError`、`KeyError` 等）的合法控制流。审查脚本需区分 `except Exception:` 与 `except SpecificError:` 才能准确识别违规。
- **P2-19 发现**：6 种语言中 4 种（de/vi/pt_BR/zh_TW）是臆测添加——无实际用户、翻译不完整、i18n 键覆盖率低。裁到 zh_CN+en 后无任何功能损失。
- **P2-17/18 发现**：mine 页面本质是「设置页的子集」——声纹入口、退出登录、关于、设置跳转，全部可合并进 settings。WorkshopHome 与 device-list 数据源相同（`v2GetDevices`），Hero 卡片设计相似，合并为零信息损失。write-draw-panel 已是 2 步简化流，create/ 是高级模式，两者并存合理。
- **T1-1 发现**：n-gram TF-IDF 方案在不引入 sentence-transformers 重型依赖的前提下实现了毫秒级语义匹配（< 1ms），准确率覆盖核心意图（coding/chat/explanation/translation）。比正则规则维护成本低一个量级。
- **T2-3 发现**：Ledger 事件流已天然支持时间线查询，无需 schema 变更——`events_for_task` 已有事件记录，只需聚合视图层。
- **验证**：Python 4391 passed / 0 failed；ruff check clean；pyright 0 errors；vue-tsc 0 errors；mp-weixin 编译成功。

## 2026-07-02 小程序 UI 审查配合核实纠偏：三项指控两项伪判一项属实（BACKLOG-P2-1）

- **背景**：瘦身审查报告提三项 UI 指控（create 937 行嵌套两层 tab、3 首页重叠、settings 744 行杂物），并附「chat 与 create 重叠」隐含问题。逐项核实源码后真伪分明。
- **属实项**：`create.vue` 937 行嵌套两层 tab — **属实**。`mode`(ai-draw/image-draw) + `aiSubMode`(text/image) 两层切换，且两路走不同 API（`generateImage` 云生图 vs `v2SubmitTask` 设备任务），合成 937 行（script 254 + template 240 + style 430，style 占 46% 大头）。应拆两页，已拆（M2）。
- **部分属实项**：3 首页重叠 — **部分属实**。mine 统计卡（设备/在线/任务 3 数字）与 index 智能体页 Hero 设备卡的数据重复；mine「设备管理」「设备配网」两菜单跳底栏已有的 tab（多 1 步冗余跳转）。已去重（M3：mine 删统计+删冗余菜单，转纯账号页；index Hero「设备 X 台」改为「在线 X/总 Y 台」吸收在线统计）。
- **伪判项 1：settings 744 行「杂物」** — **不属实**。逐区块核实，全部是设置页职责（网络设置/缓存管理/隐私权限/通知订阅/注销账号/关于我们/语言设置），无一非设置功能混入。臃肿源于 7 个 section 的标题+卡片壳样式重复未抽组件，加 `useConfigStore`/`systemInfo` 2 处死代码。已抽 `SectionCard` 组件去样式重复 + 删死代码（M1），744→655 行。
- **伪判项 2：chat 与 create 重叠** — **不属实**。chat 用 `chatCompletionStream`(文本流式 LLM)、create 用 `generateImage`+`v2SubmitTask`(生图/设备任务)，零交叉导入，入口逻辑不重复。不动。
- **教训**：审查「行数/嵌套层数」计数可信，但「杂物/重叠」定性不可信。改 UI 前必须逐区块核实每个功能点的归属（是否真在该页职责范围、是否真与它页重复），不能按行数或审查措辞盲改。

## 2026-07-02 agent 配置树合并纠偏：审查「8 棵树 9300 行重复」多数被 gitignore 不入库（BACKLOG-P1-4）

- **背景**：瘦身审查报告称「~9300 行 agent 指令跨 8 棵配置树（`.agent`/`.claude`/`.kimi-code`/`.cursor`/`.joycode`/`andrej-karpathy-skills`/根），Ponytail 规则重复 6 处」，建议合并。
- **纠偏结论**：8 棵树中 **5 棵被 `.gitignore` 忽略、不入库**（`.agent`=行361、`.claude`=行130、`.kimi-code`=行28、`.continue`=行363、`andrej-karpathy-skills`=行47）——这些是各 IDE/Agent 工具的**本地私有配置**，重复是工具生态正常现象，不应也不能「合并」。
- **真正入库的 agent 树**仅 5 个：`.cursor`(2 rules)、`.joycode`(2 memory)、`skills`(14)、`AGENTS.md`、`CLAUDE.md`。其中真正冗余的只有 `.cursor/rules/` 两份：
  - `ponytail.mdc`（`alwaysApply:true`）与 `docs/AGENTS_PONYTAIL.md`（被 `AGENTS.md` 引用为权威 Ponytail 顾问规则源）内容重复。
  - `ecc-workflow.mdc`（`alwaysApply:true`）与 `docs/ECC_WORKFLOW_CN.md`（被 `AGENTS.md` 引用为权威 ECC 流程源）内容重复。
- **处置**：删除 `.cursor/rules/ponytail.mdc` + `ecc-workflow.mdc`，`AGENTS.md` 保持单一权威源；保留 `.cursor/rules/lima-*.mdc`（未入库的本地 Cursor 私有 rules，不影响入库面）。
- **教训**：审查把「本地工具私有配置」也算入「跨树重复」是口径错误。合并前必须 `git ls-files <tree>` 区分入库与本地私有——后者重复无害、前者才是可统一项。

## 2026-07-02 静默降级审查纠偏：审查报告「16 处」实际一等生产路径仅 4 处（BACKLOG-P1-2）

- **背景**：瘦身审查报告称生产路径有 16 处 `except: pass/continue` 静默降级，点名 `voice_pipeline_ws.py`/`mqtt_client.py`/`store_voiceprint.py` 各 2 处。用 Explore 子代理逐点实地核查。
- **纠偏结论**：审查的「计数」准确（这些文件确各有 2 处 pure-swallow），但「严重度」错误——被点名的 6 处**全部合规**：
  - `voice_pipeline_ws.py`：`asyncio.TimeoutError`→continue（队列轮询超时，正常循环）、`asyncio.CancelledError`→pass（关闭时等待已取消 worker）；两处广义 `except Exception`（L123/L131）不是吞——它们 `_send_error` 后 return，worker 广义 handler（L169）有 `warning(exc_info=True)`。
  - `mqtt_client.py`：`asyncio.CancelledError`→pass（stop 时任务取消，兄弟 `except Exception`（L105）有 warning）、`asyncio.TimeoutError`→pass（消息泵 `wait_for` 超时后 drain，惯用法）；`except ImportError`（L187）不是静默——前面有两条 `_log.info`。
  - `store_voiceprint.py`：两处 `sqlite3.OperationalError`→pass 均是 schema 迁移幂等（`# column may not exist yet` / `# Column already exists`），有注释；所有广义 `except Exception`（L51/L150/L185/L208）都有 warning。
- **真正违反 AGENTS.md「禁止静默降级」的一等生产路径 = 4 处**（广义 `except Exception` 裸吞、零日志），本轮已全部修复补日志：
  - `routing_executor_parallel.py`（并行降级执行器）、`speculative_execution.py`（推测竞速内层 future）、`observability/jsonl_store.py`（读遥测文件）、`provider_automation/adapters/cloudflare.py`（编码评分循环）。
- **边界项（本轮不改，记录待排期）**：`packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64`、`pricing_probe.py:74` 各 1 处——冷离线提供商探测工具，不在生产请求路径，风险低。若后续要求「全仓零裸吞」再统一处理。
- **教训**：修静默降级不能按 grep pattern 计数盲改。窄化异常（`asyncio.TimeoutError`/`sqlite3.OperationalError`/`json.JSONDecodeError`）做控制流是合规的；只有「广义 `except Exception` + 无日志 + 无重抛」才是违规。审查报告的计数可作线索，严重度判定必须逐点复核。

## 2026-07-02 系统瘦身审查：四维度过度设计诊断 + DEPRECATED 标记误标发现

- **背景**：用户质疑「小程序交互复杂化」+「后端过度设计」。对固件/后端/文档/小程序四维度做了量化审查，确认过度设计系统性存在。详见 `docs/superpowers/specs/2026-07-02-system-slimdown-design.md`。
- **关键发现（误标 bug）**：`speculative_policy.py` 和 `capability_matrix.py` 顶部标 `# DEPRECATED v3.0 — coding capability retired`，但实际：
  - `speculative_policy.py` 的 `AFFINITY`/`classify_complexity`/`get_affinity_backends` 被 `speculative.py`（请求流水线推测执行步骤）和 `context_pipeline/complexity.py` **活跃 import 使用** —— 是热路径，非死代码。
  - `capability_matrix.py` 的 `classify_intent` 仍被 `tests/test_capability_matrix_intent.py` 测试。
  - **直接删除会导致生产崩溃**。真实情况是「coding 能力退役，但模块本身未退役」。
- **处理**：已修正两个文件的顶部注释，明确区分「coding 退役」与「模块退役」。`routes/eval_internal.py` 确为退役态（返回 410，测试断言），保持原状。
- **教训**：「DEPRECATED」标记的语义必须精确 —— 标记某个能力的退役 ≠ 标记整个文件可删。删前必须 grep 调用方 + codegraph impact 双重确认。
- **其他 P0 已完成**：修 AGENTS.md 3 处断链（reference/ECC→.claude/ecc、reference/ponytail/ 不存在）；修 STATUS.md Telegram 措辞矛盾（通知通道退役 vs gallery 存储 API 复用，两者不同）；删 `.claude/skills/gitnexus/`（与 AGENTS.md「禁止 GitNexus」冲突）；P0-2 U8 音频协议已选方案 A 并改代码。
- **U8 音频协议矛盾（P0-2，已选方案 A，代码已改）**：用户选择方案 A「固件改 PCM」。已在 U8 固件实现上下行 PCM 透传，同时保留 MQTT/Xiaozhi 的 OPUS 编解码路径不破坏：
  - `AudioStreamPacket` 新增 `format` 字段（默认 `"opus"`）；
  - `protocol.h` 新增 `UsesPcm()` 接口，`WebsocketProtocol` 返回 `true`，`MqttProtocol` 继承默认 `false`；
  - `application.cc` 在协议初始化后调用 `audio_service_.SetSendPcm(protocol_->UsesPcm())`；
  - `websocket_protocol.cc` 对下行音频包设置 `format="pcm"`；
  - `audio_service.cc` 的 `OpusCodecTask` 中：上行按 `send_pcm_` 选择 PCM 透传或 OPUS 编码；下行按 `packet->format` 选择 PCM 透传或 OPUS 解码；`PlaySound` 保持 `format="opus"`。
  - **结果**：U8 连接 LiMa 时，hello 帧 `format="pcm"` 与实际发送格式一致；后端无需新增 OPUS 解码依赖。待实际烧录 U8 后验证实时语音/TTS 回放的端到端效果。
- **BACKLOG-P0-1 已关闭**：`deploy_unified.py` 已支持 `--target {aliyun,jdcloud}`，默认 `jdcloud`，避免默认部署到旧 Aliyun pilot 而生产入口在 JDCloud 的错误。详见 `progress.md` 同日期条目。

## 2026-07-01 前端匿名聊天请求已分流至阿里云 pilot

- **结论**：chat-web、`www.donglicao.com` playground、manager-mobile H5 的匿名简单聊天请求现在会发送到 `https://aliyun.donglicao.com/v1/chat/completions`，由阿里云 `lima-router-pilot`（仅免费后端）处理。
- **实现机制**：
  - **chat-web**：`chat-web/js/app-config.js` 运行时判断无 API Key + 默认模型 + 无 tools/图片时选择 pilot；`chat-api.js` 统一通过 `LiMaConfig.getApiUrl()` 获取 URL；`sendMessage()` 在 pilot 返回 429/503/5xx 或网络错误时自动回退主节点一次。
  - **官网 playground**：`donglicao-site-v2/app/developer/playground/page.tsx` 在 API Key 为空且 endpoint/model 为默认 chat 时自动切换 baseUrl。
  - **manager-mobile**：`utils/index.ts` 新增 `getChatBaseUrl()`，未登录且默认模型时返回 `aliyun.donglicao.com`；`api/chat/chat.ts` 流式/非流式 chat 均使用该 baseUrl。
  - CSP `connect-src` 已增加 `https://aliyun.donglicao.com`。
- **部署**：
  - GitHub Actions `Deploy Chat Web` / `Deploy Next.js Site` workflow 已自动部署到 Cloudflare Pages。
  - 京东云 `/opt/lima-router/chat-web` 源文件已同步，作为 FastAPI `/chat/` 静态回源。
  - 京东云 tunnel 入口由直连 `:8080` 改为 `https://127.0.0.1:443`（跳过 TLS 校验），恢复 nginx 作为入口，从而支持 `/mobile/` H5 目录。
  - manager-mobile H5 构建 base 设为 `/mobile/` 并通过 `scp -r` 部署到 `/var/www/chat/mobile/`。
- **验证**：
  - `https://app.donglicao.com/` 与 `https://www.donglicao.com/developer/playground/` 均引用 `aliyun.donglicao.com`。
  - `https://chat.donglicao.com/mobile/index.html` 返回 H5 入口，资源路径以 `/mobile/assets/` 开头。
  - 直接 POST `aliyun.donglicao.com/v1/chat/completions`（Origin: chat.donglicao.com）返回 200，CORS 正常，后端为 `pollinations_openai`。
- **风险与后续**：
  - Cloudflare Worker 兜底/灰度方案已实施并验证：新增 `cloudflare/workers/chat-router.js`，部署到 `chat.donglicao.com/v1/chat/completions*`；无 Authorization 的匿名 chat 由 Worker 代理到 pilot（响应头 `X-Lima-Backend: aliyun`），pilot 异常时自动回源京东云（`X-Lima-Backend: jdcloud`）。
  - manager-mobile 微信小程序包尚未重新上传发版；H5 已部署。

## 2026-07-01 全栈深度质量检查（LiMa + Web + chat-web + 小程序 + 固件）

### 检查范围与结果

- **LiMa 后端**：pytest 4249 passed / 0 failed；ruff clean；pyright 0 errors；code size PASS（修复后）。
- **donglicao-site-v2**（Next.js 官网）：XSS 0、密钥泄漏 0、SEO 正确、apex→www 重定向安全。发现 1 个 MEDIUM：`public/_headers` 缺 CSP/HSTS/X-Frame-Options（仅 X-Content-Type-Options + Referrer-Policy），加固版仅存在于未启用的 `nginx-headers.conf.example`。
- **chat-web**（Cloudflare Pages 前端）：Turnstile 服务端验证正确（fail-closed）、SRI 完整、无密钥泄漏。发现 5 个 MEDIUM：(1) `_headers` 无 HSTS；(2) `'unsafe-inline' script-src` + sessionStorage token 提升 XSS 影响；(3) Turnstile site key 配置但 secret 缺失时静默放行；(4) `hash-assets.mjs` 遗漏根级 `chat-*.js`（immutable 缓存无 bust）；(5) devices.js status 插值未 escape（当前数据安全）。
- **小程序 manager-mobile**：Bearer bug 已修复、AppID 一致、HTTPS/WSS 全覆盖。发现 4 个 MEDIUM：(1) 设备转移 unionid 发送为 `toPhone` 字段（后端契约待核实）；(2) 上传文件类型验证被注释掉；(3) 登录态基于 accountId 而非 token（可能误跳转登录）；(4) 非 WeChat 端 chat streaming fallback 为死代码。
- **固件 esp32S_XYZ**：AUDIT-12 全部 6 项控制（OTA 签名/URL 白名单/WS 鉴权/坐标边界/日志脱敏）均 PRESENT 且无回归。发现 1 个 MEDIUM：`McpServer::DoToolCall` 跳过 `user_only` 执行门禁（未认证本地 WS 可 `tools/call self.reboot` DoS，固件安装仍被 F1 签名门禁阻断）。4 个 LOW：control_ws_token 无写入者（默认开放）、token 比较非常量时间、activation 失败日志含完整响应体、IDF floor 5.5.2 可升 5.5.3。

### 本次修复（3 项）

1. **`config/settings_core.py` 301 行 → 280 行**（违反 ≤300 硬规则）：提取 `get_key_pool_raw`/`resolve_backend_key`/`get_env` 三个纯函数到新 `config/settings_helpers.py`；`config/settings.py` 更新导入源。code size 检查从 FAIL → PASS。
2. **Turnstile fail-open 警告**（`device_logic/turnstile.py`）：当 `TURNSTILE_SITE_KEY` 已配置但 `TURNSTILE_SECRET_KEY` 为空时，启动日志输出 `WARNING`（之前静默放行，无任何日志）。
3. **死代码清理**（`server_lifespan_phases.py`）：移除 `start_auto_indexer`/`stop_auto_indexer` 定义（commit `ba3d64ee` 已移除调用但保留了函数定义）。

### 待跟进项（需独立排期）

- ~~**donglicao-site-v2 `_headers`**~~：✅ 已完成（2026-07-01 第二轮修复：补 CSP/HSTS/X-Frame-Options/Permissions-Policy）。
- ~~**chat-web `hash-assets.mjs`**~~：✅ 已完成（2026-07-01 第二轮修复：扩展哈希覆盖根级 `chat-*.js`）。
- ~~**chat-web `_headers`**~~：✅ 已完成（2026-07-01 第二轮修复：补 HSTS）。
- ~~**6 个 SAFE dependabot PR**~~：✅ 已手动应用（fastapi 0.138.2、python-multipart 0.0.32、pyright 1.1.411、pytest-timeout 2.4、httpx 0.28.1、websockets 16.0）。
- **小程序设备转移 `toPhone` 字段**：核实后端契约是否期望 unionid。
- **固件 `DoToolCall` user_only 门禁**：在执行路径增加 `user_only` 检查。
- **4 个 RISKY dependabot PR**（torch/torchaudio/dashscope/onnxruntime）建议关闭。
- **7 个需独立审查 PR**（eslint-10/typescript-6/types-node-26/react/tailwindcss/vue/wrangler-action/setup-node）。

### 第二轮修复（2026-07-01，commit 49f55b61）

- **`client_keys/storage.py`**：`update_usage()` 改为 raise `ClientKeyStorageError`（不再静默吞 sqlite3.Error）；`import json` 提到模块级。
- **`access_guard.py`**：`_dynamic_auth_configured` 从 bare `Exception` 收窄为 `(ImportError, AttributeError)`。
- **`device_logic/wechat_gateway.py`**：`response.json()` 移入 try/except（ValueError 捕获）；`import time` 提到模块级。
- **`routes/client_keys.py`**：4 个 mutation 端点返回 typed `KeyMutationResponse`（`response_model_exclude_none=True`）。
- **合并重复测试**：`test_security_headers.py` 删除，唯一 `csp_is_strict` 测试并入 `test_routes_security_headers.py`。

## 2026-07-01 Dependabot / pip-audit 依赖漏洞修复

- **扫描结果**：本地 `.venv310` 运行 `pip-audit --local` 发现 5 个包共 17 个已知漏洞：
  - `cryptography 48.0.0` → GHSA-537c-gmf6-5ccf（OpenSSL 静态链接漏洞）
  - `Pillow 10.4.0` → CVE-2026-25990 / CVE-2026-40192 / CVE-2026-42308 / CVE-2026-42310 / CVE-2026-42311
  - `pip 23.0.1` → CVE-2023-5752 / CVE-2025-8869 / CVE-2026-1703 / CVE-2026-3219 / CVE-2026-6357 / CVE-2026-8643
  - `python-multipart 0.0.30` → CVE-2026-53540（负 Content-Length 导致无界读取）
  - `starlette 1.2.1` → CVE-2026-54282 / CVE-2026-54283（urlencoded 表单限制绕过、URL 主机欺骗）
- **修复操作**：
  - 升级本地 venv：`pip==26.1.2`, `cryptography==48.0.1`, `Pillow==12.2.0`, `python-multipart==0.0.31`, `starlette==1.3.1`。
  - 收紧 `requirements_server.txt`：
    - `python-multipart>=0.0.31,<1.0`
    - `Pillow~=12.2.0`
    - 新增显式下限：`starlette>=1.3.1`（FastAPI 传递依赖）、`cryptography>=48.0.1`（Paramiko 传递依赖）。
- **验证**：
  - `pip-audit --local` → `No known vulnerabilities found`。
  - 聚焦 Pillow 相关测试：`tests/test_svg_converter.py`, `tests/test_svg_converter_sketch.py`, `tests/test_svg_binarize.py` → 33 passed。
  - 聚焦 FastAPI/Starlette 相关测试：`tests/test_device_app_auth.py`, `tests/test_routes_chat_preflight.py`, `tests/test_routing_engine_post.py` → 25 passed。
  - 完整门禁 `scripts/run_pre_commit_check.py --full` → 4239 passed, 3 skipped, ruff 通过。
- **扩展修复（esp32S_XYZ 子模块）**：
  - 子模块仓库同步提交并 push 到 `zhuguang-ZFG/esp32S_XYZ`。
  - `esp32S_XYZ/requirements.txt`：`pytest>=9.0.3`（CVE-2025-71176）。
  - `esp32S_XYZ/firmware/u8-xiaozhi/scripts/Image_Converter/requirements.txt`：`Pillow~=12.2.0`。
- **扫描工具误报说明**：
  - 运行 `pip-audit` 时，本地杀毒软件将 `cyclonedx-python-lib` 的 `vulnerability.cpython-310.pyc` 误报为 `HEUR:HackTool/VulnScan.a` 并删除。
  - 已执行 `--force-reinstall pip-audit` 恢复，`pip-audit --local` 再次运行正常。
- **扩展修复（前端与容器）**：
  - `donglicao-site-v2/package.json`：添加 `overrides` 强制 `postcss>=8.5.10`；`npm audit` 归零，`npm run build` 成功。
  - `docs-site/pnpm-workspace.yaml`：添加 `overrides` 强制 `vite ^6.4.3`、`esbuild ^0.25.0`；`pnpm audit` 归零，`pnpm run build` 成功。
  - `Dockerfile`：基础镜像从浮动 `python:3.10-slim` 固定为 `python:3.10.20-slim-bookworm@sha256:89cef4d55961e885def21b86e34e102e65b7eab8cd281e806a66ff1709c9a455`。
- **额外修复**：
  - `.github/workflows/test.yml`：将错误的 `actions/checkout@v7`、`actions/setup-python@v6`、`actions/cache@v6` 改为正确的 v4/v5/v4。
  - 2026-07-01 新增 CI `pip-audit -r requirements_server.txt` 门禁（`PYTHONUTF8=1`），与 `bandit` 合并到 `Security scan` 步骤。
- **仍未修复的告警**：
  - GitHub push 后仍提示 default branch 有 16 个漏洞（7 high, 9 moderate）。本地可扫描的 manifests 已全部 clean，剩余可能来源：
    - GitHub Dependabot 计数存在延迟/缓存。
    - `esp32S_XYZ` 子模块中其他未扫描的旧 npm/pnpm/Dockerfile manifests（如 `u1-grbl/embedded` 仍有 33 个高危/严重级漏洞，`xiaozhi-esp32-server/main/manager-mobile` 因私有 registry 无法 audit）。
    - Dockerfile 固定 digest 后仍可能存在 Debian 系统级未修补 CVE。
- **风险与后续**：
  - Pillow 大版本 10→12 已确认通过全部图像处理测试；生产部署后需观察 `xiaozhi_drawing/svg_converter.py` 与 `device_logic/captcha.py` 行为。
  - pip 大版本 23→26 仅影响包安装流程，未引入运行时变更。
  - ~~建议后续在 CI 中加入 `pip-audit --requirement requirements_server.txt` 门禁。~~ ✅ 已完成（2026-07-01）：`.github/workflows/test.yml` 新增 `pip-audit -r requirements_server.txt` 步骤，环境变量 `PYTHONUTF8=1` 规避 Windows 编码问题。
  - 子模块中遗留的旧前端构建链（gulp/cheerio/underscore 等）如需继续修复，涉及直接依赖大版本升级，可能破坏 ESP32 固件构建流程，需单独评估。


## 2026-07-02 external_enrichment provider 占位状态确认

- `external_enrichment/providers/nager_date.py` 与 `open_meteo.py` 方法体仅返回硬编码 mock（`# TODO: Actual API call would go here`）。
- 确认：两文件被 `tests/test_external_enrichment.py` 明确用作离线测试 mock（docstring 标注 "offline tests with mock"）。
- 结论：保留，不为瘦身删除测试依赖。真实 API 接入留待功能驱动时再做（YAGNI）。

## 2026-07-02 CodeGraph 死函数复审（13 个候选）

> 候选来自瘦身审查「疑似 0 调用点函数」清单。用 CodeGraph `edges.target` fan-in + 全库 grep 双重确认。

### 删除（12 个，CodeGraph fan-in=0 且 grep 全库无调用点、无装饰器、无同文件引用）

| 文件:行 | 函数 | 说明 |
|---------|------|------|
| token_health.py:110 | `alert_expired_tokens` | 疑似未接 cron，无调用方 |
| model_registry.py:108 | `get_active` | 与 key_pool.get_active_count 名字近但无关联 |
| backends_registry/__init__.py:85 | `get_backend` | 与 health_state.get_backend_* 名字近但无关联 |
| device_gateway/mqtt_client.py:34 | `is_mqtt_enabled` | 调用方直接读 DEVICE.mqtt_enabled |
| device_gateway/mqtt_client.py:46 | `mqtt_send_to_device` | async 投递函数，无调用方 |
| context_pipeline/cache.py:74 | `build_cached_prompt` | 仅改 _metrics 统计，无调用方 |
| route_scorer.py:97 | `task_fit_score` | 编码退役后纯函数无调用方 |
| user_identity/lessons.py:66 | `apply_lesson` | 有文件写副作用但无任何调用方 |
| context_compressor.py:165 | `estimate_context_usage` | 纯计算，无调用方 |
| session_memory/compactor.py:121 | `llm_summarizer_factory` | 工厂函数，无注入式调用方 |
| channel_retirement.py:17 | `is_retired_route_path` | 纯函数，无调用方 |
| key_pool.py:251 | `provider_snapshot` | 委托 pool_snapshot，无调用方（与 provider_automation/snapshot_store 模块名近但无关联） |

### 保留（1 个）

| 文件:行 | 函数 | 保留原因 |
|---------|------|----------|
| observability/prometheus_metrics.py:199 | `record_backend_error` | 有测试覆盖（test_observability_metrics.py:90），疑似预留 prometheus 调度入口，YAGNI 保守保留 |

### 验证
- ruff check 11 个文件 clean
- check_code_size PASS
- 聚焦测试 64 passed（test_token_health/test_model_registry/test_backend_registry/test_route_scorer/test_channel_retirement/test_key_pool）
