# Git & Deploy — Git 纪律与部署

## Git 硬规则

- **禁止** `git add .`；仅 stage 本次里程碑相关文件。
- 禁止暂存凭证、`.env`、`.lima-data/`。
- 禁止未经用户许可 force-push / reset。
- commit message 用 conventional commits。
- **用户未要求时不 commit**（`.trellis/config.yaml` 已设 `session_auto_commit: false`，journal 不自动提交）。

## 里程碑协作协议

```
1. 用户实现里程碑切片
2. Agent 审查 → 测试 → git diff --check
3. 更新 progress.md / findings.md
4. 仅 stage 相关文件 → commit → push
5. 推送后再提议下一里程碑
```

自动结项（用户未说「不要部署/提交」时）：pytest → VPS 部署 → 文档同步 → commit/push。

## 部署

- 默认目标京东云：`python scripts/deploy_unified.py --target jdcloud`（`get_deploy_target()` 默认 `jdcloud`；脚本双节点、容量感知、自动备份）。
- 增量部署示例：`--files device_voice/ routes/device_app_voice.py ...`。
- 运行时目录 `/opt/dlc-drawing/`；回滚取 `/opt/dlc-drawing/backups/`；systemd 单元 `dlc-drawing`。
- 部署拓扑：Internet → Cloudflare → 京东云 `117.72.118.95`（nginx → :8081 + Redis）；阿里云为历史 pilot。

## Closeout（发布收尾）

完整 7 步见 `docs/DEPLOY_AND_RELEASE_CONVENTION.md`：本地门禁 → 变更审查 → VPS 部署 → VPS 验证（**必须真实域名 + token，禁止自动降级验证**）→ 证据落盘（`progress.md`/`findings.md`）→ Git Commit → GitHub 上传。

## 小程序发布（esp32S_XYZ 子模块）

`manager-mobile` 变更走一键上传流程（vue-tsc → uni build → 微信开发者工具 CLI upload → 提审），命令与注意事项见 `docs/AGENTS_REFERENCE_CN.md`「常用命令」。
