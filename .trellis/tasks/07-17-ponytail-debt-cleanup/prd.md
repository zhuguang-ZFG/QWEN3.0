# Ponytail 硬门禁债务清理

## 目标
对 DLC 后端 4 个轻微超长的函数做纯重构抽取，使全库函数 ≤50 行（Ponytail 硬门禁）。不改外部行为。

## 背景（巡检取证 2026-07-17）
AST 扫描 213 个 .py（server_dlc.py / dlc_api / dlc_core / device_gateway / device_voice / dlc_mcp / routes / scripts）：

- 文件 ≤300 行：**0 违例** ✅
- ruff：**No issues found** ✅
- 静默吞异常：扫描器报 6 处，**逐条复核全部为窄类型有意写法，0 真实违例**——
  `routes/device_app_notifications.py:31`（json 解析回退）、`scripts/deploy_unified_deploy.py:118,:165`（OSError 临时清理）、`scripts/deploy_unified_restart.py:213`（json 健康检查重试）、`scripts/eval_device_model_role.py:187`（reconfigure 跨版本）、`scripts/smoke_device_app_voice_e2e.py:38`（ImportError 可选依赖）。扫描器只判 pass-only 函数体未区分裸 except，误报率 100%，**不改**。
- 函数 ≤50 行：**4 处轻微超（51–63 行）** → 本任务目标。

## 范围（已锁：4 个全改，严格 ≤50 合规）

| 函数 | 现状 | 抽取方案 | 预估 |
|------|------|----------|------|
| `device_gateway/device_write_handler.py:93 handle_device_write` | 61 行（含 20 行 docstring） | 抽 `_failed_write_result(error)`，合并 L120-128 / L145-152 两处重复 failed-dict | ~-16 行 |
| `routes/device_app_assets.py:203 render_asset` | 53 行 | 抽 `_asset_render_response(task, asset_id, dispatch)`，承载 L246-255 末尾 ok() 载荷 | ~-9 行 → ~44 |
| `device_gateway/handwriting_path.py:50 try_text_to_handwriting` | 51 行 | 抽 `_handwriting_result(result, status, error, *, preset=False, font=None)`，合并 L80-89 / L90-99 两处返回 dict | ~-15 行 |
| `scripts/deploy_unified_deploy.py:205 remove_remote_files` | 63 行 | 抽 `_build_rm_command(remote, parent, stem)`（L242-256）+ `_safe_remote_rel(raw)` 路径净化 | ~-15 行 |

约束：仅模块内新增私有 helper，函数签名/返回结构/API 响应/下发逻辑/部署产物**全部不变**。

## 验收标准
- AC1：上述 4 个函数 AST 复测全部 ≤50 行
- AC2：`ruff check` 通过（No issues found） ✅
- AC3：相关 pytest 通过——device_gateway / routes / scripts 各自既有测试 ✅
- AC4：纯重构——4 个函数对外签名未变，无新增 import 副作用 ✅

## 执行结果（2026-07-17）
实现链：Reasonix 首轮抽 6 个 helper（Atom/Reasonix 后续派发均因桥接层 240s 天花板取消，转为 Claude 直改 + 复核）。
Claude 复核抓到并修复 3 处问题：
1. handwriting_path `_handwriting_result`：`if font is not None` → `if status == "success"`（success 分支恒带 font 键，failed 分支无）
2. device_app_assets `_asset_render_response`：加 status 参数，复用 dispatch 前算好的 status，不在 helper 内重算
3. deploy_unified_deploy：remove_remote_files 抽 helper 降 53→44 行。pre-commit 复核发现新建的 `_connect_ssh` 与 `deploy_unified_restart._connect_ssh` **逐字重复**——改为复用现成的（同时消除 `_deploy_with_sftp` 的重复连接块），文件 317→296 行过 ≤300 门禁；`tests/test_deploy_unified.py` 的 patch 目标随之从 deploy 改到 restart 命名空间。

最终 AST（主函数/helper）：handle_device_write 45/_failed_write_result 11、render_asset 44/_asset_render_response 14、try_text_to_handwriting 36/_handwriting_result 22、remove_remote_files 44（_connect_ssh 复用自 deploy_unified_restart）/_build_rm_command 12/_safe_remote_rel 6。
ruff No issues；pyright 0 error；check_code_size PASS（全库 0 文件>300、0 函数>50）；pytest（write_handler/assets/handwriting_fallback/deploy_unified/deploy_transaction/deploy_common）37 passed。

## 验证命令
```bash
# 行数复测
python -c "<AST 重测 4 个函数>"
ruff check device_gateway/device_write_handler.py routes/device_app_assets.py device_gateway/handwriting_path.py scripts/deploy_unified_deploy.py
pytest tests/ -k "device_write or asset or handwriting or deploy"  # 按实际测试命名调整
```

## 回滚
纯重构无 schema/迁移，回滚 = `git checkout -- <4 个文件>`。

## Out of scope
- 静默异常（已证 0 真实违例）
- 圈复杂度 / 重复代码 / 死代码 / 类型标注 / 测试缺口（属"扩大审计面"，另开）
