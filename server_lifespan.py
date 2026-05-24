"""FastAPI lifespan orchestration for LiMa Server."""

from contextlib import asynccontextmanager

import http_caller
import probe_loop


@asynccontextmanager
async def lifespan(application):
    """Start and stop background runtime helpers."""
    probe_loop.start(probe_fn=http_caller.probe)
    try:
        from session_memory.daemon import start_daemon

        await start_daemon()
    except ImportError:
        pass
    try:
        from routes.telegram import start_telegram_webhook

        await start_telegram_webhook()
    except ImportError:
        pass
    try:
        yield
    finally:
        probe_loop.stop()
        try:
            from session_memory.daemon import stop_daemon

            await stop_daemon()
        except ImportError:
            pass
