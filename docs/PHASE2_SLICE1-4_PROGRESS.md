# Phase 2 Slice 1-4 执行报告

**日期**: 2026-06-12
**任务**: smart_router.py 迁移计划 - Slice 1-4
**状态**: ✅ 完成

---

## 执行摘要

成功完成 smart_router 迁移的前 4 个 Slice，涉及 60+ 处引用的迁移：

| Slice | 范围 | 文件数 | 引用数 | 状态 |
|-------|------|--------|--------|------|
| Slice 1 | 后端配置迁移 | 5 | 18+ | ✅ 完成 |
| Slice 2 | 路由分类器迁移 | 3 | 5 | ✅ 完成 |
| Slice 3 | 意图检测迁移 | 3 | 4 | ✅ 完成 |
| Slice 4 | 熔断器迁移 | 4 | 4 | ✅ 完成 |

**总计**: 15 个文件，31+ 处引用迁移

---

## Slice 1: 后端配置迁移

### 目标
迁移 `smart_router.BACKENDS` 及相关配置到 `backends.BACKENDS`

### 修改文件
1. `routes/admin_backends.py` (2 处)
2. `routes/admin_api.py` (7 处)
3. `routes/admin_api_extra.py` (6 处)
4. `routes/system_endpoints.py` (1 处)
5. `routes/chat_support.py` (3 处)

### 变更内容
- 替换 `import smart_router` → `import backends`
- 迁移 `BACKENDS`, `VISION_BACKENDS`, `GFW_BACKENDS`, `THINKING_BACKENDS`
- 移除 `admin_api_extra.py` 中的降级处理（ImportError fallback）

### 验证结果
- ✅ 编译检查通过
- ✅ Ruff 检查通过
- ✅ 全量测试 2008 passed
- ✅ 无残留引用（生产代码）

### Git 提交
```
refactor(Phase2-Slice1): 迁移 smart_router.BACKENDS → backends.BACKENDS
```

---

## Slice 2: 路由分类器迁移

### 目标
迁移 `smart_router.analyze` 到 `router_classifier.analyze`

### 修改文件
1. `orchestrate.py` (1 处 analyze + 3 处注释)
2. `routes/chat_handler_dispatch.py` (2 处 analyze)
3. `tests/test_prompt_memory_recall.py` (2 处测试 mock 修复)

### 变更内容
- 替换 `smart_router.analyze` → `router_classifier.analyze`
- 更新注释中的 `smart_router.route` → `routing_engine.route`
- 修复测试：monkeypatch `router_classifier.analyze` 而不是 `server.smart_router.analyze`

### 关键发现
测试使用 `monkeypatch.setattr(server.smart_router, "analyze", fake_analyze)` 来 mock，但代码现在直接使用 `router_classifier.analyze`，导致 mock 不生效。解决方案：修改测试直接 mock `router_classifier.analyze`。

### 验证结果
- ✅ 编译检查通过
- ✅ Ruff 检查通过
- ✅ 全量测试 2008 passed
- ✅ test_prompt_memory_recall.py 2 个测试修复

### Git 提交
```
refactor(Phase2-Slice2): 迁移 smart_router.analyze/route → router_classifier/routing_engine
```

---

## Slice 3: 意图检测迁移

### 目标
迁移意图检测函数到专门的模块

### 修改文件
1. `routes/chat_handler_dispatch.py` (2 处: detect_thinking_intent, detect_image_intent)
2. `routes/chat_stream.py` (1 处: detect_image_intent)
3. `routes/chat_support.py` (1 处: get_thinking_backend)

### 变更内容
- 替换 `smart_router.detect_thinking_intent` → `router_intent.detect_thinking_intent`
- 替换 `smart_router.detect_image_intent` → `router_image.detect_image_intent`
- 替换 `smart_router.get_thinking_backend` → `router_intent.get_thinking_backend`

### 保留的兼容层验证
- `test_router_image.py::test_detect_image_intent_reexported_via_smart_router`
- `test_vision_routing.py::test_has_vision_content_delegates_to_detect_vision_request`

这些测试验证 `smart_router` 作为兼容层的正确性，应该保留。

### 验证结果
- ✅ 编译检查通过
- ✅ Ruff 检查通过
- ✅ 全量测试 2008 passed
- ✅ test_router_image.py + test_vision_routing.py 6 passed

### Git 提交
```
refactor(Phase2-Slice3): 迁移意图检测 smart_router → router_intent/router_image
```

---

## Slice 4: 熔断器迁移

### 目标
迁移熔断器函数到 `router_circuit_breaker`

### 修改文件
1. `routes/admin_api.py` (1 处 cb_status)
2. `routes/system_endpoints.py` (1 处 cb_status)
3. `routes/chat_support.py` (1 处 cb_allow)
4. `routes/health_dashboard.py` (1 处 cb_status)

### 变更内容
- 替换 `smart_router.cb_status` → `router_circuit_breaker.cb_status`
- 替换 `smart_router.cb_allow` → `router_circuit_breaker.cb_allow`

### 验证结果
- ✅ 编译检查通过
- ✅ Ruff 检查通过
- ✅ 全量测试 2008 passed
- ✅ test_admin_paths.py + test_system_endpoints.py 10 passed

### Git 提交
```
refactor(Phase2-Slice4): 迁移熔断器 smart_router.cb_* → router_circuit_breaker.cb_*
```

---

## 剩余工作

### Slice 5: HTTP 调用迁移（计划中）

需要迁移的引用：
1. `orchestrate.py`: `smart_router.call_local` (2 处)
2. `routes/chat_support.py`: `smart_router.call_api` (2 处)
3. `routes/chat_post_closeout.py`: `smart_router._log_to_distill_queue` (1 处)
4. `tests/test_vision_routing.py`: `smart_router.call_api` (1 处)

目标模块：`router_http.call_api`, `router_local.call_local`

### 后续 Slice

**配置/常量迁移**：
- `smart_router.ROUTE` → 路由表模块
- `smart_router.PUBLIC_MODEL_NAME` → 配置模块
- `smart_router.DEBUG` → 配置模块
- `smart_router.DISTILL_QUEUE_DIR` → 配置模块
- `smart_router.warmup_router_model()` → 初始化模块

**最终清理**：
- 移除 `smart_router.py` 的兼容层导出
- 更新所有注释和文档中的 `smart_router` 引用

---

## 质量保证

### 测试覆盖
- 每个 Slice 完成后运行全量测试（2008 个测试）
- 所有测试 100% 通过
- 特定模块测试单独验证

### 代码质量
- 所有修改通过 `python -m py_compile` 编译检查
- 所有修改通过 `ruff check` 静态检查
- 无新增 lint 警告

### Git 管理
- 每个 Slice 独立提交
- 提交信息清晰，包含范围、变更、验证结果
- 所有提交已推送到 GitHub (`origin/main`)

---

## 关键经验

### 1. 测试 Mock 的依赖注入问题

**问题**: 测试通过 `monkeypatch.setattr(server.smart_router, "analyze", fake)` 来 mock，但代码现在直接导入并使用 `router_classifier.analyze`，导致 mock 不生效。

**解决**: 修改测试直接 mock 目标模块的函数：
```python
# 错误（mock 不生效）
monkeypatch.setattr(server.smart_router, "analyze", fake_analyze)

# 正确（直接 mock 目标模块）
import router_classifier
monkeypatch.setattr(router_classifier, "analyze", fake_analyze)
```

**教训**: 迁移时需要同步更新测试的 mock 目标。

### 2. 兼容层验证的重要性

保留了多个测试专门验证 `smart_router` 作为兼容层的正确性：
- `test_analyze_reexported_via_smart_router`
- `test_detect_image_intent_reexported_via_smart_router`
- `test_has_vision_content_delegates_to_detect_vision_request`

这些测试确保旧代码（如果存在）仍然可以通过 `smart_router` 调用新模块。

### 3. 渐进式迁移的优势

每个 Slice 都是独立的、可验证的单元：
- 范围清晰，易于理解
- 失败时容易定位和回滚
- 提交历史清晰，便于 Code Review

---

## 下一步行动

1. **继续执行 Slice 5**: HTTP 调用迁移（`call_api`, `call_local`）
2. **配置/常量迁移**: 将配置相关的常量移到专门的配置模块
3. **最终清理**: 移除兼容层，更新文档

**预计时间**: Slice 5 约 1-2 小时，完整迁移约 4-6 小时

---

**报告生成时间**: 2026-06-12
**执行人**: Claude Opus 4.8
**状态**: ✅ Slice 1-4 完成，进度 50%
