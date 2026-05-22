# Code Quality Correctness Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 只闭环已经核实为真实、且会直接影响正确性或请求证据质量的问题，不在这一轮启动大范围重构。

**Architecture:** 本轮沿用当前兼容路径，先补回归测试，再做最小实现。`smart_router` 复用现有视觉检测逻辑，`server` 从请求处理起点计算真实耗时，并把统计日志中的外部 IP 位置查询移出锁；对本地一次性部署脚本只增加防误提交护栏和验证，不在未获确认时删除用户文件。验证通过后再回填项目状态、长期记忆和执行证据。

**Tech Stack:** Python 3, FastAPI, pytest, PowerShell, existing LiMa router modules.

---

### Scope

- 接受 `docs/CODE_QUALITY_REPORT.md` 中已经核实的事实：`smart_router.py:885` 调用 `_has_vision_content(msgs)`，但当前文件没有该函数；同文件底部已有 `detect_vision_request(messages: list) -> bool`。
- 接受 Anthropic vision 统计缺陷：`server.py` 当前计算 `int((time.time() - time.time()) * 1000)`，随后又把 vision 请求耗时按 `0` 写入 `_record_request()`，导致延迟证据失真。
- 接受统计锁性能缺陷：`_record_request()` 在持有 `_stats_lock` 时调用 `_get_ip_location(client_ip)`；后者可能发起外部 HTTP 请求，超时为 `0.5s`。
- 接受本地敏感脚本风险：当前工作区有未跟踪的一次性 deploy/test/upload Python 脚本带密码样字面量，必须避免误 stage 和误 commit；已跟踪的 `deploy_v3.py` 当前已经走环境变量或密钥路径，不把它归类为本轮明文密码修复。

### Non-Goals

- 不在本轮拆分 `server.py`。
- 不在本轮统一 `BACKENDS` 单一来源。
- 不在本轮合并 `server.py` 与 `response_builder.py` 的重复响应构造逻辑。
- 不在本轮迁移 `smart_router` 熔断状态与 `health_tracker` 双系统。
- 不做支付、公共注册、商业 quota、usage、billing 或 dashboard。
- 本计划默认只做本地修复与验证；除非用户在本地验证后明确要求，否则不部署 VPS。

### File Map

- Create: `tests/test_vision_routing.py`
  - 负责 `cf_vision` 图片内容检测与视觉调用分支回归。
- Create: `tests/test_request_stats.py`
  - 负责耗时辅助函数和 `_record_request()` 锁边界回归。
- Modify: `smart_router.py`
  - 暴露一个与现有视觉检测逻辑一致的 `_has_vision_content()` 路径，供 `call_api()` 使用。
- Modify: `server.py`
  - 记录 Anthropic vision 的真实耗时，并把 IP 位置查询移出 `_stats_lock`。
- Modify: `.gitignore`
  - 忽略已经出现过的一次性本地 deploy/test/upload 脚本族，降低误提交敏感字面量风险。
- Modify after verification: `STATUS.md`, `docs/LIMA_MEMORY.md`, `progress.md`
  - 回填报告结论、修复证据、延期项和验证结果。

### Task 1: 修复 cf_vision 图片内容检测断链

**Files:**
- Create: `tests/test_vision_routing.py`
- Modify: `smart_router.py` near `call_api()` and `detect_vision_request()`

- [x] **Step 1: 写失败测试**

在 `tests/test_vision_routing.py` 添加回归：

```python
import smart_router


def _image_messages():
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,abc"},
                },
            ],
        }
    ]


def test_has_vision_content_delegates_to_detect_vision_request():
    assert smart_router._has_vision_content(_image_messages()) is True
    assert smart_router._has_vision_content(
        [{"role": "user", "content": "plain text"}]
    ) is False


def test_call_api_routes_cf_vision_with_image_content(monkeypatch):
    monkeypatch.setattr(smart_router, "cb_allow", lambda _name: True)
    monkeypatch.setitem(
        smart_router.BACKENDS,
        "cf_vision",
        {
            "key": "test",
            "auth": "bearer",
            "fmt": "openai",
            "url": "https://example.test",
            "model": "vision",
        },
    )
    monkeypatch.setattr(
        smart_router,
        "_call_cf_vision",
        lambda _msgs, _mt, _t0: "vision-ok",
    )

    assert smart_router.call_api("cf_vision", _image_messages()) == "vision-ok"
```

- [x] **Step 2: 跑测试确认当前失败**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_vision_routing.py -q --ignore=active_model
```

Expected: FAIL，失败信息指向缺少 `_has_vision_content` 或 `NameError`。

- [x] **Step 3: 写最小实现**

把别名辅助函数放在 `smart_router.py` 的 `detect_vision_request()` 附近，让图片判断只保留一份真实逻辑：

```python
def _has_vision_content(messages: list) -> bool:
    """Return True when OpenAI-format messages contain image blocks."""
    return detect_vision_request(messages)
```

- [x] **Step 4: 跑测试确认修复**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_vision_routing.py -q --ignore=active_model
```

Expected: `2 passed`。

- [x] **Step 5: 提交独立修复**

```powershell
git -C D:\GIT add smart_router.py tests\test_vision_routing.py
git -C D:\GIT commit -m "fix: restore cf vision content detection"
```

### Task 2: 修复 Anthropic vision 耗时统计

**Files:**
- Create or extend: `tests/test_request_stats.py`
- Modify: `server.py` near helper functions and Anthropic `/v1/messages` vision branch

- [x] **Step 1: 为耗时辅助函数写失败测试**

在 `tests/test_request_stats.py` 添加：

```python
import server


def test_elapsed_ms_clamps_and_reports_real_duration(monkeypatch):
    monkeypatch.setattr(server.time, "time", lambda: 12.5)
    assert server._elapsed_ms(10.0) == 2500

    monkeypatch.setattr(server.time, "time", lambda: 9.0)
    assert server._elapsed_ms(10.0) == 0
```

- [x] **Step 2: 跑测试确认当前失败**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_stats.py::test_elapsed_ms_clamps_and_reports_real_duration -q --ignore=active_model
```

Expected: FAIL，失败信息包含缺少 `server._elapsed_ms`。

- [x] **Step 3: 添加最小耗时实现并替换错误统计**

在 `server.py` 的 helper 区添加：

```python
def _elapsed_ms(started_at: float) -> int:
    return max(0, int((time.time() - started_at) * 1000))
```

在 Anthropic `/v1/messages` 处理函数进入后、图片分支开始前只记录一次请求起点：

```python
request_started_at = time.time()
```

把 vision 成功分支中的错误统计替换为：

```python
duration_ms = _elapsed_ms(request_started_at)
_record_request(
    last_user_query or "[vision]",
    backend_used,
    "vision",
    duration_ms,
    True,
    client_ip=client_ip,
    ide_source=ide_source,
    sys_prompt_preview=sys_prompt_preview,
)
```

- [x] **Step 4: 确认旧坏表达式已消失**

Run:

```powershell
rg -n "time\.time\(\) - time\.time\(\)|_record_request\(.*\"vision\", 0" D:\GIT\server.py
```

Expected: 没有匹配项。

- [x] **Step 5: 跑耗时测试**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_stats.py -q --ignore=active_model
```

Expected: `test_elapsed_ms_clamps_and_reports_real_duration` 通过。

- [x] **Step 6: 提交独立修复**

```powershell
git -C D:\GIT add server.py tests\test_request_stats.py
git -C D:\GIT commit -m "fix: record anthropic vision latency"
```

### Task 3: 把 IP 位置查询移出统计锁

**Files:**
- Extend: `tests/test_request_stats.py`
- Modify: `server.py` in `_record_request()`

- [x] **Step 1: 写锁边界失败测试**

继续在 `tests/test_request_stats.py` 添加：

```python
def test_record_request_looks_up_country_before_stats_lock(monkeypatch):
    observed_locks = []

    def record_location(_ip):
        observed_locks.append(server._stats_lock.locked())
        return "test-country"

    monkeypatch.setattr(server, "_get_ip_location", record_location)
    monkeypatch.setattr(
        server,
        "_stats",
        {
            "total_requests": 0,
            "backend_calls": {},
            "intent_distribution": {},
            "recent_logs": [],
        },
    )

    server._record_request(
        "query",
        "backend",
        "chat",
        7,
        client_ip="203.0.113.7",
    )

    assert observed_locks == [False]
    assert server._stats["recent_logs"][-1]["country"] == "test-country"
```

- [x] **Step 2: 跑锁边界测试确认当前失败**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_stats.py::test_record_request_looks_up_country_before_stats_lock -q --ignore=active_model
```

Expected: FAIL，锁观察值仍为 `[True]`。

- [x] **Step 3: 写最小实现**

在 `_record_request()` 进入锁前完成位置查询：

```python
country = _get_ip_location(client_ip) if client_ip else ""

with _stats_lock:
    ...
    log_entry = {
        ...
        "country": country,
        ...
    }
```

- [x] **Step 4: 重跑锁边界测试**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_stats.py::test_record_request_looks_up_country_before_stats_lock -q --ignore=active_model
```

Expected: PASS。

- [x] **Step 5: 跑整份统计回归**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_stats.py -q --ignore=active_model
```

Expected: 文件内全部测试通过。

- [x] **Step 6: 提交独立修复**

```powershell
git -C D:\GIT add server.py tests\test_request_stats.py
git -C D:\GIT commit -m "perf: keep location lookup outside stats lock"
```

### Task 4: 降低本地一次性脚本误提交风险

**Files:**
- Modify: `.gitignore`
- Do not delete untracked files without explicit user approval

- [x] **Step 1: 先确认脚本是否已被 Git 跟踪**

Run:

```powershell
git -C D:\GIT ls-files deploy_r8_test.py deploy_test_r4.py run_remote_test.py upload_r6.py upload_r13.py deploy_v3.py
```

Expected: 当前只看到 `deploy_v3.py`。

- [x] **Step 2: 给一次性本地脚本加 ignore 护栏**

在 `.gitignore` 添加：

```gitignore
# One-off local deploy probes may contain operator credentials.
deploy_test_*.py
deploy_r*_test.py
run_remote_test.py
upload_r*.py
```

- [x] **Step 3: 检查工作区可见性变化**

Run:

```powershell
git -C D:\GIT status --short
```

Expected: 上述一次性脚本不再作为待 stage 文件出现；其他无关未跟踪文件可以继续存在。

- [x] **Step 4: 做敏感字面量扫描并人工判读**

Run:

```powershell
rg -n "zhuguang110|password\s*=|ssh\.connect\(.*password" D:\GIT -g "*.py" -g "!active_model/**" -g "!**/*-ref/**"
```

Expected: 必须人工检查输出；任何已跟踪文件命中都阻断提交。含密码样字面量的未跟踪文件仍只是本地清理候选，不在本任务中自动删除或 stage。

- [x] **Step 5: 单独提交 ignore 护栏**

```powershell
git -C D:\GIT add .gitignore
git -C D:\GIT commit -m "chore: ignore one-off deploy probes"
```

Task 4 follow-up note: the safety review expanded beyond ignore rules. Tracked `scripts/` files were scrubbed so hardcoded `sk-` token literals are read from environment variables instead.

### Task 5: 回填质量报告结论与验证证据

**Files:**
- Modify: `STATUS.md`
- Modify: `docs/LIMA_MEMORY.md`
- Modify: `progress.md`

- [x] **Step 1: 记录本轮报告判定**

在状态和证据文档中写清：

```markdown
- accepted/fixed: cf_vision `_has_vision_content` 断链。
- accepted/fixed: Anthropic vision 请求耗时写成 0。
- accepted/fixed: `_record_request()` 在统计锁内做 IP 位置查询。
- rejected/outdated: admin API 完全无认证、`deploy_v3.py` 明文密码、`test_streaming.py` 不可执行。
- deferred: `server.py` 分拆、`BACKENDS` 单一来源、response builder 去重、健康状态系统迁移。
```

- [x] **Step 2: 跑本地验证门**

Run:

```powershell
git -C D:\GIT diff --check
D:\GIT\venv\Scripts\python.exe -m py_compile smart_router.py server.py
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_vision_routing.py tests\test_request_stats.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py test_http_caller.py test_rate_limiter.py test_streaming.py tests\test_coding_eval.py tests\test_lima_context.py tests\test_anthropic_tool_protocol.py tests\test_route_scorer.py tests\test_free_web_ai_probe.py tests\test_free_web_ai_admission.py tests\test_access_guard.py tests\test_fallback_context.py tests\test_ide_detection.py tests\test_image_endpoint_guard.py tests\test_stream_footer.py tests\test_vision_routing.py tests\test_request_stats.py -q --ignore=active_model
```

Expected: `diff --check` 和 `py_compile` 无错误，选定测试全部通过；把实际通过数量写回证据文档，不预填猜测值。

- [x] **Step 3: 只 stage 本轮目标文件**

Run:

```powershell
git -C D:\GIT diff --cached --name-only
```

Expected: 只包含本轮源码、测试、`.gitignore` 和证据文档；不包含 `.claude/`、参考仓库、一次性脚本、本地凭据或压缩包。

- [x] **Step 4: 提交证据更新**

```powershell
git -C D:\GIT add STATUS.md docs\LIMA_MEMORY.md progress.md
git -C D:\GIT commit -m "docs: close code quality hardening evidence"
```

### Verification Gate

- 本轮完成声明前必须先跑 Task 5 的本地验证门。
- 若测试新增或文件边界调整，先更新计划 checkbox 和证据，再做额外提交。
- 本计划不默认部署。
- 若后续用户明确要求部署，执行顺序必须是：部署前备份，上传本地已验证文件，远端编译，restart，health，公开接口 smoke，鉴权接口 smoke，记录回滚点。

### Deferred Follow-Up Plans

- 单独编写 `BACKENDS` 单一来源计划，并先核对旧路径与 V3 路径实际使用面。
- 单独编写 response builder 去重与 `server.py` 小切片拆分计划，按路由边界拆，不做一次性巨改。
- 单独编写健康状态系统迁移计划，先定义 `smart_router.cb_*` 与 `health_tracker` 的过渡契约。

### Report Accuracy Decision

- `docs/CODE_QUALITY_REPORT.md` 可作为候选审计输入，不应直接视为事实源。
- 本计划只吸收已经复核成立的问题：视觉检测断链、vision 耗时证据失真、统计锁内外部位置查询，以及未跟踪一次性脚本的防误提交风险。
- 已复核为过时或表述不准确的结论不进入修复任务：管理 API 完全无认证、`deploy_v3.py` 明文密码、旧 streaming 测试不可执行。
- 大型架构结论需要拆成独立、可验证的后续计划，不能借报告标题直接扩成一轮混合重构。
