# Gitee 双 Remote 镜像 Runbook（GI-G-1）

Updated: 2026-05-26

## 目标

`git push` 同时更新 GitHub 与 Gitee；任一侧失败可观测、可告警。

## 推荐 push 方式

```powershell
# 顺序 push origin → gitee，失败 exit 1
python scripts/push_dual_remotes.py

# 失败时 Telegram 告警（需 bot 配置 + FRP 7897 可用）
python scripts/push_dual_remotes.py --notify

# 仅预览
python scripts/push_dual_remotes.py --dry-run
```

Shell：

```bash
./scripts/push_dual_remotes.sh --notify
```

## 手动双 push

```powershell
git push origin HEAD
git push gitee HEAD
```

若 `origin` 已配置两个 push URL，单次 `git push origin` 也会推两次；**仍建议**用 `push_dual_remotes.py` 以便分 remote 报错。

## 凭证

- GitHub：HTTPS + PAT 或 SSH
- Gitee：HTTPS + 私人令牌（`oauth2:<token>@gitee.com/...`）
- **勿**将 token 写入仓库；使用 git credential manager 或本地 `.git/config`（已在 `.gitignore` 范围外）

## LFS / 大文件

- 确认 Gitee 仓库 LFS 配额与 GitHub 一致
- 首次 mirror 大历史可用 `git push --all` + `git push --tags` 分批

## 失败告警

`telegram_notify.notify_ops_event()` ← `push_dual_remotes.py --notify`

依赖 **TG-GH-1** FRP 7897 隧道；出站不可达时告警也会失败——配合 `scripts/smoke_telegram_outbound.py` cron。

## 回滚

镜像 push 失败 **不会** 回滚已成功的一侧；修复 remote 后重跑 `push_dual_remotes.py` 即可。

## 相关

- Baseline：`docs/GITEE_BASELINE.md`
- Telegram 出站：`docs/TELEGRAM_BOT_DESIGN.md` § FRP Runbook
