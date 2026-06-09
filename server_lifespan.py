"""FastAPI lifespan orchestration for LiMa Server."""

import logging
from contextlib import asynccontextmanager

import http_caller
import probe_loop
from channel_retirement import retire_telegram_webhook_from_env

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application):
    """Start and stop background runtime helpers."""
    # Load persisted health state
    try:
        import health_state
        loaded = health_state.load_health_state()
        _log.info("Loaded health state: %d backends", loaded)
    except ImportError as exc:
        _log.warning("health_state module not loaded; persisted health state skipped: %s", exc)

    # Load persisted backend profiles
    try:
        import backend_profile
        loaded = backend_profile.load_profiles()
        _log.info("Loaded backend profiles: %d", loaded)
        backend_profile.save_on_interval(300)
    except ImportError as exc:
        _log.warning("backend_profile module not loaded; persisted backend profiles skipped: %s", exc)

    # Load retired backends
    try:
        import backend_retirement
        loaded = backend_retirement.load_retired()
        _log.info("Loaded retired backends: %d", loaded)
    except ImportError as exc:
        _log.warning("backend_retirement module not loaded; retired backend state skipped: %s", exc)

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
    await retire_telegram_webhook_from_env()
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
        from observability.prometheus_metrics import validate_startup
        from observability.prometheus_exporter import start_exporter

        validate_startup()
        start_exporter()
    except ImportError as exc:
        _log.warning("prometheus metrics modules not loaded; metrics exporter skipped: %s", exc)
    except RuntimeError as exc:
        _log.error("prometheus metrics startup validation failed: %s", exc)
        raise
    try:
        yield
    finally:
        probe_loop.stop()
        try:
            from observability.prometheus_exporter import stop_exporter

            stop_exporter()
        except ImportError:
            _log.debug("prometheus_exporter stop skipped")
        try:
            from context_pipeline.auto_indexer import stop_auto_indexer

            stop_auto_indexer()
        except ImportError as exc:
            _log.debug("auto_indexer stop skipped; module not loaded: %s", exc)
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
