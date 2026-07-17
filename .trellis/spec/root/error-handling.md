# Error Handling & Logging — 错误处理与日志

## 硬规则：无静默降级

- **禁止** `except: pass` / `except Exception: pass`，也禁止裸 `except:`。
- 捕获后至少 `logger.warning(...)`，并明确后续语义（重试、降级返回、或 re-raise）。
- 生产路径必须正确配置；禁止用吞异常伪装「可选功能」。
- 安全审查基线：P0/HIGH/MEDIUM/LOW 已闭环（`STATUS.md`），新增代码不得低于该水位。

## 本地惯用法（照此写）

**启动期 fail-fast** — 配置失败直接终止，不带病运行：

```python
# server_dlc.py lifespan
try:
    configure_task_store_from_env()
except Exception:
    logger.error("task store configuration failed", exc_info=True)
    raise
```

**未配置即显式异常** — 用领域异常，不返回空结果：

```python
# device_voice/asr.py
if not VOICE.enabled:
    raise AsrNotConfiguredError("LIMA_VOICE_ENABLED is not set")
```

**关停/清理路径** — 单个资源失败记 warning 后继续清理其余（证据：`server_dlc.py` 优雅关停段，`logger.warning(..., exc_info=True)`）。

**一次性 ticket / 短效凭证** — 鉴权校验用 `peek`；失败路径（槽满、依赖未配置、ASR `session.start` 失败等）不得烧票。Voice：仅在 ASR `session.start` 成功后再 `consume`（证据：`device_app_voice_ws`，任务 `07-17-backend-prelaunch-p1`）；Status 等其它 WS 仍可在 accept 前、槽与依赖就绪后 consume（证据：`device_app_status_ws`，任务 `07-17-ws-ticket-status-p2`）。

**外部 HTTP** — 统一用 httpx；图生等阻塞调用经 `asyncio.to_thread`（证据：`dashscope_image_client.py`）。

## 反模式

- `dlc_core/` 目前**没有** `except Exception` —— 核心层保持干净，异常在边界（API 路由、入口 lifespan）处理。不要在核心层加兜底 try/except。
- 不要新增 `except Exception: return None/[]/{}` 式静默降级；需要降级时记日志并让调用方可见。

## 日志模式

- 仅在入口处配置：`server_dlc.py` 的 `logging.basicConfig(level=logging.INFO, ...)`；业务模块一律 `logger = logging.getLogger(__name__)`。
- `LIMA_STRUCTURED_LOGGING=1` 时入口切换 `observability.structured_logging.setup_structured_logging`（唯一保留的 observability 模块）。
- 异常日志带 `exc_info=True`；不在库代码里用 `print`。
