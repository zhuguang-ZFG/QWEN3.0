# Gitee Baseline（GI-G-0）

Updated: 2026-05-26

## 角色

| 托管 | 角色 | 说明 |
|------|------|------|
| **GitHub** (`origin`) | 主仓 | Submodule 治理、LiMa Code 契约、CQ-GH-001 webhook |
| **Gitee** (`gitee` + `origin` 第二 push URL) | 国内镜像 | 国内访问、备用 clone、后续 GI-G-2 webhook |

## 当前 remote 形态（示例，勿提交 token）

典型配置：

```text
origin   fetch → https://github.com/<owner>/<repo>.git
origin   push  → https://github.com/<owner>/<repo>.git
           push  → https://gitee.com/<owner>/<repo>.git   # 双 push
gitee    fetch/push → https://gitee.com/<owner>/<repo>.git
```

检查命令：

```powershell
python scripts/gitee_mirror_status.py
python scripts/gitee_mirror_status.py --json
```

输出中的 URL **已脱敏**（`oauth2:***`）。

## 与 GitHub 事件对比

| 事件 | GitHub | Gitee | LiMa 现状 |
|------|--------|-------|-----------|
| Push | ✅ webhook | ✅ WebHook | GitHub ✅ / Gitee ❌ GI-G-2 |
| Pull Request | ✅ | ✅ Merge Request | GitHub ✅ |
| CI fail | ✅ workflow_run | ✅ Pipeline（企业/Go） | GitHub ✅ |
| Issues | ✅ | ✅ | 均未接 Telegram |
| 代码评审触发 CI | ❌ | ✅ | 未接 |

## 模力方舟 AI（GI-G-3 前置）

- API：`https://ai.gitee.com/v1/chat/completions`（OpenAI 兼容）
- 需要：`GITEE_AI_TOKEN`（模力方舟 Access Token）
- **当前：未接入 LiMa 路由**

## 下一刀

- GI-G-1：[`GITEE_MIRROR_RUNBOOK.md`](GITEE_MIRROR_RUNBOOK.md)
- GI-G-2：`POST /gitee/webhook` → Telegram

## 相关

- 计划：`docs/superpowers/plans/2026-05-26-gitee-maximization.md`
- GitHub 对称：`docs/GITHUB_WEBHOOK_INTEGRATION.md`
