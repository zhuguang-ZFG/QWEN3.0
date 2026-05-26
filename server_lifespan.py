"""FastAPI lifespan orchestration for LiMa Server."""

import logging
from contextlib import asynccontextmanager

import http_caller
import probe_loop

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application):
    """Start and stop background runtime helpers."""
    try:
        from backend_admission_store import apply_startup

        apply_startup()
    except ImportError:
        _log.debug("backend_admission_store not installed")
    probe_loop.start(probe_fn=http_caller.probe)
    try:
        import periodic_coding_eval

        periodic_coding_eval.start()
    except ImportError:
        _log.debug("periodic_coding_eval not installed")
    try:
        from session_memory.daemon import start_daemon

        await start_daemon()
    except ImportError:
        _log.debug("session_memory.daemon not installed")
    try:
        from routes.telegram import start_telegram_webhook

        await start_telegram_webhook()
    except ImportError:
        _log.debug("routes.telegram not installed")
    try:
        from routes.device_gateway import start_device_gateway_runtime

        await start_device_gateway_runtime()
    except ImportError:
        _log.debug("routes.device_gateway runtime not installed")
    try:
        yield
    finally:
        probe_loop.stop()
        try:
            import periodic_coding_eval

            periodic_coding_eval.stop()
        except ImportError:
            _log.debug("periodic_coding_eval stop skipped")
        try:
            from session_memory.daemon import stop_daemon

            await stop_daemon()
        except ImportError:
            _log.debug("session_memory.daemon stop skipped")
        try:
            from routes.device_gateway import stop_device_gateway_runtime

            await stop_device_gateway_runtime()
        except ImportError:
            _log.debug("device_gateway runtime stop skipped")
