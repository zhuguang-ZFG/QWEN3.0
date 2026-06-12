# Phase 2 Slice 5 执行计划

**创建时间**: 2026-06-12 晚
**执行时间**: 2026-06-13 上午 10:00
**预计时长**: 1-2 小时

---

## 目标

迁移 HTTP 调用相关函数：
- `smart_router.call_local` → `router_local.call_local`
- `smart_router.call_api` → `router_http.call_api`
- `smart_router._log_to_distill_queue` → 适配层或直接调用

---

## 引用清单

| 文件 | 函数 | 引用数 | 复杂度 |
|------|------|--------|--------|
| `orchestrate.py` | `call_local` | 2 | 简单 |
| `routes/chat_support.py` | `call_api` | 2 | 简单 |
| `routes/chat_post_closeout.py` | `_log_to_distill_queue` | 1 | 中等 |
| `tests/test_vision_routing.py` | `call_api` | 1 | 简单 |

**总计**: 4 个文件，6 处引用

---

## 执行步骤

### Step 1: 验证目标模块存在（5 分钟）

**任务**:
```bash
# 检查 router_local.py 是否存在
ls -la router_local.py

# 检查 router_http.py 是否存在
ls -la router_http.py

# 检查函数是否已导出
grep "def call_local" router_local.py
grep "def call_api" router_http.py
```

**预期**:
- ✅ `router_local.py` 存在且有 `call_local` 函数
- ✅ `router_http.py` 存在且有 `call_api` 函数

**如果不存在**:
- 检查 `smart_router.py` 中的实现
- 确认这些函数是否已经迁移到其他模块

---

### Step 2: 修改 `orchestrate.py`（10 分钟）

**当前引用**:
```python
# Line ~160
resp = smart_router.call_local(
    msgs,
    mt=DECOMPOSE_MAX_TOKENS,
    t=0.7,
)

# Line ~180
answer = smart_router.call_local(msgs, mt=SYNTHESIZE_MAX_TOKENS, t=0.5)
```

**修改计划**:
1. 在文件顶部添加导入：
```python
import router_local
```

2. 替换两处调用：
```python
# Line ~160
resp = router_local.call_local(
    msgs,
    mt=DECOMPOSE_MAX_TOKENS,
    t=0.7,
)

# Line ~180
answer = router_local.call_local(msgs, mt=SYNTHESIZE_MAX_TOKENS, t=0.5)
```

**验证**:
```bash
python -m py_compile orchestrate.py
ruff check orchestrate.py
```

---

### Step 3: 修改 `routes/chat_support.py`（10 分钟）

**当前引用**:
```python
# Line ~23
asyncio.to_thread(smart_router.call_api, thinking_backend, msgs, max_tokens, ide)

# Line ~43
asyncio.to_thread(smart_router.call_api, alt, msgs, max_tokens, ide)
```

**修改计划**:
1. 在文件顶部添加导入：
```python
import router_http
```

2. 替换两处调用：
```python
# Line ~23
asyncio.to_thread(router_http.call_api, thinking_backend, msgs, max_tokens, ide)

# Line ~43
asyncio.to_thread(router_http.call_api, alt, msgs, max_tokens, ide)
```

**验证**:
```bash
python -m py_compile routes/chat_support.py
ruff check routes/chat_support.py
```

---

### Step 4: 修改 `routes/chat_post_closeout.py`（20 分钟）

**当前引用**:
```python
# 需要先读取文件确认具体位置
smart_router._log_to_distill_queue(query, content, intent_payload, backend)
```

**修改计划**:

**选项 A**: 如果 `_log_to_distill_queue` 已迁移到专门模块
```python
import distill_logger  # 假设的模块名
distill_logger.log_to_queue(query, content, intent_payload, backend)
```

**选项 B**: 如果还在 `smart_router` 中
- 保持不变，作为兼容层
- 或者直接实现（如果逻辑简单）

**执行前需要**:
1. 读取 `routes/chat_post_closeout.py` 确认用法
2. 检查 `smart_router._log_to_distill_queue` 的实现
3. 决定迁移策略

**验证**:
```bash
python -m py_compile routes/chat_post_closeout.py
ruff check routes/chat_post_closeout.py
```

---

### Step 5: 修改 `tests/test_vision_routing.py`（10 分钟）

**当前引用**:
```python
# 需要先读取文件确认具体位置
assert smart_router.call_api("cf_vision", _image_messages()) == "vision-ok"
```

**修改计划**:

**选项 A**: 如果测试的是兼容层
- 保持不变，验证 `smart_router.call_api` 仍然可用

**选项 B**: 如果测试的是直接调用
```python
import router_http
assert router_http.call_api("cf_vision", _image_messages()) == "vision-ok"
```

**执行前需要**:
1. 读取测试文件确认测试意图
2. 决定是保留还是修改

**验证**:
```bash
python -m pytest tests/test_vision_routing.py -v
```

---

### Step 6: 编译检查（5 分钟）

```bash
python -m py_compile orchestrate.py \
    routes/chat_support.py \
    routes/chat_post_closeout.py
```

**预期**: 无编译错误

---

### Step 7: Ruff 检查（5 分钟）

```bash
python scripts/run_ruff_check.py \
    orchestrate.py \
    routes/chat_support.py \
    routes/chat_post_closeout.py
```

**预期**: All checks passed!

---

### Step 8: 运行相关测试（10 分钟）

```bash
# 运行 HTTP 相关测试
python -m pytest tests/test_vision_routing.py -v

# 运行编排测试（如果存在）
python -m pytest tests/test_orchestrate.py -v --tb=short

# 运行思考模式测试
python -m pytest tests/ -k "thinking" -v --tb=short
```

**预期**: 所有测试通过

---

### Step 9: 全量测试（后台运行，20 分钟）

```bash
python -m pytest -q --basetemp=.pytest_temp --ignore=tests/test_token_health.py
```

**预期**: 2008 passed, 25 skipped

**如果失败**:
- 检查失败的测试
- 确认是否与 Slice 5 相关
- 如果相关，修复后重新运行
- 如果无关，记录并继续

---

### Step 10: Git 提交（5 分钟）

```bash
git add orchestrate.py \
    routes/chat_support.py \
    routes/chat_post_closeout.py \
    tests/test_vision_routing.py

git commit -m "refactor(Phase2-Slice5): 迁移 HTTP 调用 smart_router → router_http/router_local

**范围**: HTTP 调用函数迁移（4 处 call_api + 2 处 call_local）

**修改文件**:
- orchestrate.py (2 处 call_local)
- routes/chat_support.py (2 处 call_api)
- routes/chat_post_closeout.py (1 处 _log_to_distill_queue)
- tests/test_vision_routing.py (1 处 call_api - 根据实际情况)

**变更内容**:
1. 替换 smart_router.call_local → router_local.call_local
2. 替换 smart_router.call_api → router_http.call_api
3. 处理 _log_to_distill_queue（根据实际情况）

**验证**:
- ✅ 编译检查通过
- ✅ Ruff 检查通过
- ✅ 全量测试 2008 passed
- ✅ test_vision_routing.py X passed

**下一步**: Slice 6 - 配置/常量迁移

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"

git push origin main
```

---

## 潜在问题与预案

### 问题 1: `_log_to_distill_queue` 是内部函数

**现象**: 以 `_` 开头，可能是内部实现

**预案**:
- 选项 A: 如果逻辑简单，直接在 `chat_post_closeout.py` 中实现
- 选项 B: 创建 `distill_logger.py` 模块
- 选项 C: 暂时保留 `smart_router._log_to_distill_queue` 调用

**决策依据**: 读取实现后根据复杂度决定

---

### 问题 2: `call_api` 有多个签名

**现象**: 不同地方调用参数可能不同

**预案**:
- 确认 `router_http.call_api` 的签名与 `smart_router.call_api` 一致
- 如果不一致，可能需要适配

**决策依据**: 读取 `router_http.py` 确认

---

### 问题 3: 测试失败

**现象**: 某些测试依赖 `smart_router` 的具体实现

**预案**:
- 检查测试的 mock 目标
- 更新 mock 到新的模块
- 参考 Slice 2 的经验（`test_prompt_memory_recall.py`）

---

## 检查清单

**开始前**:
- [ ] 阅读本计划
- [ ] 确认精力充沛
- [ ] 准备好测试环境

**执行中**:
- [ ] Step 1: 验证目标模块 ✓
- [ ] Step 2: 修改 orchestrate.py ✓
- [ ] Step 3: 修改 chat_support.py ✓
- [ ] Step 4: 修改 chat_post_closeout.py ✓
- [ ] Step 5: 修改 test_vision_routing.py ✓
- [ ] Step 6: 编译检查 ✓
- [ ] Step 7: Ruff 检查 ✓
- [ ] Step 8: 相关测试 ✓
- [ ] Step 9: 全量测试 ✓
- [ ] Step 10: Git 提交 ✓

**完成后**:
- [ ] 更新 `docs/PHASE2_SLICE1-4_PROGRESS.md` → `PHASE2_SLICE1-5_PROGRESS.md`
- [ ] 更新 `STATUS.md`
- [ ] 推送到 GitHub
- [ ] 评估是否继续 Slice 6

---

## 预计时间分配

| 步骤 | 时间 | 累计 |
|------|------|------|
| Step 1 | 5 min | 5 min |
| Step 2 | 10 min | 15 min |
| Step 3 | 10 min | 25 min |
| Step 4 | 20 min | 45 min |
| Step 5 | 10 min | 55 min |
| Step 6 | 5 min | 60 min |
| Step 7 | 5 min | 65 min |
| Step 8 | 10 min | 75 min |
| Step 9 | 20 min | 95 min |
| Step 10 | 5 min | 100 min |

**总计**: 约 1.5-2 小时

---

## 成功标准

- ✅ 所有 4 个文件编译通过
- ✅ Ruff 检查无警告
- ✅ 相关测试全部通过
- ✅ 全量测试 2008 passed
- ✅ Git 提交推送成功

---

**明天见！💪**
