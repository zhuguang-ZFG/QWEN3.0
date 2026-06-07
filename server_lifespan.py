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
    try:
        from health_bootstrap import bootstrap_runtime_health

        bootstrap_runtime_health()
    except ImportError:
        _log.debug("health_bootstrap not installed")
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

    # Telegram webhook disabled (user request: rarely used)
    # try:
    #     from routes.telegram import start_telegram_webhook
    #     await start_telegram_webhook()
    # except ImportError:
    #     _log.debug("routes.telegram not installed")

    try:
        from routes.device_gateway import start_device_gateway_runtime

        await start_device_gateway_runtime()
    except ImportError:
        _log.debug("routes.device_gateway runtime not installed")
    try:
        from observability.structured_logging import setup_structured_logging

        setup_structured_logging()
    except ImportError:
        _log.debug("observability.structured_logging not installed")

    # Register the asyncio event loop for SSE log fan-out.
    try:
        import asyncio

        from routes.admin_api import _set_sse_event_loop

        _set_sse_event_loop(asyncio.get_running_loop())
    except Exception as exc:
        _log.debug("SSE event loop registration skipped", exc_info=True)
    try:
        from device_gateway.mqtt_client import start_mqtt_client

        await start_mqtt_client()
    except ImportError:
        _log.debug("device_gateway.mqtt_client not installed")
    try:
        from context_pipeline.auto_indexer import start_auto_indexer

        start_auto_indexer()
    except ImportError:
        _log.debug("auto_indexer not installed")
    try:
        from opencode_config import log_config_summary

        log_config_summary()
    except ImportError:
        _log.debug("opencode_config not installed")
    try:
        yield
    finally:
        probe_loop.stop()
        try:
            from context_pipeline.auto_indexer import stop_auto_indexer

            stop_auto_indexer()
        except ImportError:
            _log.debug("server_lifespan: optional module not available", exc_info=True)
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
        try:
            from device_gateway.mqtt_client import stop_mqtt_client

            await stop_mqtt_client()
        except ImportError:
            _log.debug("mqtt_client stop skipped")
        # Close httpx client pools to prevent FD leaks
        try:
            from http_request_builder import _async_client_pool, _sync_client_pool

            for client in _sync_client_pool.values():
                try:
                    client.close()
                except Exception as exc:
                    _log.debug("sync client close: %s", exc)
            _sync_client_pool.clear()
            for client in _async_client_pool.values():
                try:
                    await client.aclose()
                except Exception as exc:
                    _log.debug("async client close: %s", exc)
            _async_client_pool.clear()
            _log.debug("httpx client pools closed")
        except ImportError:
            pass
        # Close SQLite connections
        try:
            from sqlite_manager import close_all as _close_sqlite

            closed = _close_sqlite()
            if closed:
                _log.debug("sqlite connections closed: %d", closed)
        except ImportError:
            pass
