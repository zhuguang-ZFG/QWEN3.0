# Findings（仅近期）

> 更早 findings / AUDIT 已删除；需要时查 git history。
> 五问法：现象？复现？根因？修复？如何预防？

## 2026-07-23 code review 低优先级项收尾（PR #74 / #75）

- **范围**：code review 明细 `docs/CODE_REVIEW_2026-07-22_CN.md` 中遗留的 #1（统一 `DEFAULT_WORKSPACE_MM`）、#3（拆分 `path_pipeline.py` SVG 渲染）、#5（`route_evidence_builder` / `draw_prompt_memory` 测试盲区）、#2（`SafetyError` 裸字符串 vs `MotionErrorCode` 枚举双轨制）。
- **处理**：
  - #1 / #3 合并为 PR #74 合并进 `main`：`DEFAULT_WORKSPACE_MM` 统一源为 `device_intelligence/schemas.py` 的 `300×300×80`；新增 `device_gateway/path_preview.py` 承载 SVG 渲染，`path_pipeline.py` 248 行。
  - #5 补直接单测：19 新增用例（`test_route_evidence_builder.py` 10 + `test_draw_prompt_memory.py` 9）。`route_evidence_builder` 此前被高层集成覆盖，但边界分支无直接测试；`draw_prompt_memory` 是完全盲区，其 `session_memory` 缺失路径为“有声降级”而非静默 `except: pass`。
  - #2 经调查改为**文档收敛**：`safety.validate_run_path_params` 在生产链路零调用，双轨矛盾只存在于内部/测试层。在 `device_gateway/safety.py` 加 module docstring 明确生产派发走 `path_validator` + `MotionErrorCode` 枚举，防止后人误将 raise 风格接入派发链丢失结构化错误码。
- **验证**：pytest 2016 passed / 0 failed；ruff + size gate PASS；VPS 健康探针 200。
- **预防**：review 低优先级项若约定“要干完”，则统一走独立 worktree → 代码 → 测试 → 合并 → 部署 → 验证 → 证据落盘；不自然遗漏。

## 2026-07-23 VPS 部署 deploy_unified 重启阶段 SSH 断连（已恢复）

- **现象**：`scripts/deploy_unified.py --target jdcloud --slice core --sync-nginx` 成功上传 262 文件并同步 nginx 后，在重启服务阶段抛 `paramiko.ssh_exception.SSHException: SSH session not active`。
- **根因**：paramiko 在上传阶段复用/新建的 SSH session 在 `restart_server` 调用 `_prepare_dependencies` 探针时已被服务器关闭；该阶段 `key auth` 已不被服务器接受，后续 fallback 没有发生（脚本在该次连接对象上直接失败）。
- **影响**：代码文件已覆盖为新版本，但进程仍为旧版本；服务处于“文件新、进程旧”的半部署状态，存在潜在不一致风险。
- **修复**：用 `.env` 中 `LIMA_JDCLOUD_ROOT_PASSWORD` 以密码认证 SSH 登录，手动执行 `systemctl restart dlc-drawing`，并轮询 `/health/ready` 直至 `{'status':'ok'}`；服务版本号 `0.4.0-p3` 为 package 版本，与 git 无关。
- **预防**：
  - 未来部署前确认 key auth 可用；不可用时应直接改用密码 auth 或修复 authorized_keys。
  - 考虑在 `deploy_unified_restart.py` 对 `SSH session not active` 做 reconnect 重试，避免已上传文件后重启失败。
  - 半部署状态 SOP：要么成功重启加载新文件，要么从 `/opt/dlc-drawing/backups/<label>/runtime-before.tgz` 回滚；禁止放任文件与进程不一致。

## 2026-07-22 全量深度 code review（明细见 `docs/CODE_REVIEW_2026-07-22_CN.md`）

- 329 py 文件 / 7 并行 agent。0 CRITICAL、15 HIGH、~47 MEDIUM、~67 LOW。
- 无密钥入库、无 SQL 注入、行数规则未违反。
- 生产风险优先级：SSRF allowlist 绕过 → 运动 `profile=None` fail-open → 认证 fail-open(空上传密钥/admin token 无吊销) → motion_event 缺 ownership → 写字 pen-up 丢失。

## 2026-07-21 文档编码损坏（docs/README）

- **现象**：`docs/README.md` 中文乱码（UTF-8 被当 ANSI 写回）。
- **根因**：清理 trailing whitespace 时用 `WriteAllText` 未指定 UTF-8。
- **修复**：整文件 UTF-8 重写；后续写中文 md 用工具默认 UTF-8。
- **预防**：PowerShell 写 md 使用 UTF8Encoding(false) 或由 `write` 工具落盘。

## 2026-07-21 bare registry 误标 complete（已修 `80fd0749`）

- **现象**：`register_device_profile` 空 `profile_id` 会使 `complete=True`，打开路由门控。
- **修复**：complete 需非空 `profile_id` + 正有限 workspace；shadow 永不 complete。
- **预防**：profile 接线 hello 前保持该判定。

## 2026-07-21 工作区 0 轴被接受（已修）

- **现象**：zero workspace 进入 path gen 后 normalize 才炸。
- **修复**：`_as_workspace` / `workspace_axes_ok` 拒绝 ≤0 / 非有限；explicit 须三轴齐全。

## 2026-07-09 静态分析门禁

- pyright venv 配置 + pytest P13 跳过 node_modules 断链；当时 pyright 0 errors / pytest 绿。

## 2026-07-06 设备网关 WSS 投递

- 曾结论「无存量设备」；**2026-07-21 起 M1/M2 已实现** DLC 侧 WSS 投递，真机联调仍为 P0-3。勿再按「已退役」理解当前代码。
