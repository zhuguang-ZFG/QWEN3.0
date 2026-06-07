# LiMa 项目开发规范

个人编码助手后端（非商业化开放平台）。**权威参考见 `AGENTS.md`。**

## Superpowers 原则

1. **文档先行**：非 trivial 改动先写设计文档（`docs/`）。
2. **文件小而专注**：单文件目标 ≤300 行；函数目标 ≤50 行。
3. **本地验证再部署**：本地测试通过后再一次性替换 VPS 文件。
4. **永不破坏生产**：可回滚；新模块独立文件，确认后再接入主路径。
5. **参考业界实践**：设计决策尽量有开源参考或实测佐证。
6. **渐进式替换**：新旧并行，小流量验证后再全量。

## 技术栈

Python 3.10 + FastAPI + uvicorn + httpx + SQLite

## 关键命令

```powershell
.venv310\Scripts\python.exe -m pytest tests/ -q --tb=short  # 测试
ruff check .                                                   # lint
python server.py                                               # 启动
python scripts/deploy_unified.py                               # 部署
python scripts/repo_stats.py                                   # 统计
```

完整命令、架构、模块所有权、环境变量见 `AGENTS.md`。
