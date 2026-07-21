# 写字/绘图机稳定性计划

> 更新日期：2026-07-21
> 依据：`ARCHITECTURE.md` + `STATUS.md`（旧「routing_engine 多后端」表已作废）

## 已具备（现行）

| 能力 | 位置 |
|------|------|
| 路径生成 / 工作区 | `path_workspace` / `path_pipeline` |
| 绘图 | `device_draw_handler` → DashScope / 预设 / 预检 |
| 写字 / 手写 | `task_handwriting_params`、本地 fallback |
| 任务队列 + 投递 | Redis + WSS M1/M2 + `delivery_reaper` |
| 运动安全 | GW-R3 bounds / feed / handwriting fail-closed |
| Host SIL | fz `agent_gate` |

## 仍要加强

| 项 | 说明 |
|----|------|
| 真机 E2E | STATUS P0-3 |
| HIL 纸路 | G3 |
| Profile 接线 | hello → `register_device_profile` |
| 手写外部依赖 | autohanding 失败已有本地 ASCII fallback；中文路径依赖持续观察 |
| 可观测 | 以 server_dlc 日志 + 现有探针为主，勿恢复旧 observability 大盘 |

## 门禁

```powershell
python -m pytest tests/ -q
ruff check .
# 运动相关改动：
python $env:FZ_ROOT\scripts\agent_gate.py --profile standard
```
