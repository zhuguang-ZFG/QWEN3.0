# LiMa Real-Machine Smoke Runbook

## Purpose

Verify LiMa Server and LiMa Code can complete one controlled real-machine worker loop without risking production or user repositories.

## Preconditions

- LiMa Server is reachable through `https://chat.donglicao.com`.
- `LIMA_CODE_SERVER_URL` points to the LiMa Server base URL, without `/v1`.
- `LIMA_CODE_API_KEY` is configured.
- LiMa Code is installed from the current local fork.
- The test repository is disposable or a temporary git repo.
- Run `/lima doctor` before executing any task.

## Recommended Smoke

Use read-only review first:

```powershell
D:\GIT\venv\Scripts\python.exe scripts\create_lima_smoke_task.py --repo D:\GIT\deepcode-cli --kind review
```

Then in LiMa Code:

```text
/lima doctor
/lima task TASK_ID_FROM_SCRIPT
/lima audit --last 5
```

## Patch Smoke

Only use this in a temporary disposable repo:

```powershell
D:\GIT\venv\Scripts\python.exe scripts\create_lima_smoke_task.py --repo D:\GIT\lima-smoke-temp --kind patch_readme
```

Then in LiMa Code:

```text
/lima doctor
/lima task TASK_ID_FROM_SCRIPT
/lima audit --last 5
```

Expected result:

- Task status becomes `needs_review`.
- Local `.lima-code/audit.jsonl` records the task.
- Server `/agent/tasks/TASK_ID_FROM_SCRIPT/events` includes `created` and `result_submitted`.
- No commits are created.
- No deployment occurs.

## Stop Conditions

Stop and investigate if:

- `/lima doctor` returns any `fail`.
- Server preflight is unreachable.
- Task repo is not allowlisted.
- The worker stop marker is pending.
- The task tries to touch files outside the target repo.
