#!/usr/bin/env python3
"""Deploy OpenCode optimization files to VPS."""

import os
import time

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.path.expanduser("~/.ssh/id_ed25519")

# Files to deploy
FILES = [
    # Existing OpenCode Phase 1
    "opencode_config.py",
    "context_compressor.py",
    "skills_injector.py",
    "model_resolver.py",
    "routing_selector.py",
    "speculative.py",
    "backends_constants.py",
    "http_response.py",
    "http_stream.py",
    "streaming_events.py",
    "routing_engine.py",
    "routing_executor.py",
    "routes/chat_stream.py",
    "routes/chat_endpoints.py",
    "routes/responses_endpoints.py",
    "converters/responses_api.py",
    "routes/chat_handler_dispatch.py",
    "routes/system_endpoints.py",
    # Round 2 deep adaptation
    "opencode_error_adapter.py",  # NEW: overflow detection + error response
    "opencode_message_normalizer.py",  # NEW: message normalization pipeline
    "http_errors.py",  # MODIFIED: BackendError.is_overflow
    "http_sync.py",  # MODIFIED: overflow detection + usage thread safety
    "http_async.py",  # MODIFIED: reasoning_effort passthrough
    "http_request_builder.py",  # MODIFIED: normalize_messages + reasoning_effort
    "response_builder.py",  # MODIFIED: usage parameter
    "chat_models.py",  # MODIFIED: reasoning_effort field
    "routes/chat_handler.py",  # MODIFIED: 413 overflow response
    "routes/v3_adapters.py",  # MODIFIED: headers/reasoning_effort/usage
    "router_http_body.py",  # MODIFIED: normalize_messages integration
    "http_caller.py",  # MODIFIED: facade re-exports (_get_client etc.)
    # Round 3 deep adaptation (M-OC3)
    "reasoning_variants.py",  # NEW: reasoning_effort/thinking tier mapping
    "session_options.py",  # NEW: per-model session options injection
    # M-OC12: tool guard + step checkpoint
    "tool_guard.py",  # NEW: doom loop detection + tool output truncation
    "step_checkpoint.py",  # NEW: per-step agent checkpointing
    # Slice 3: distill queue extraction
    "distill_queue.py",  # NEW: extracted from smart_router.py L155–228
    "local_router.py",  # Slice 4: warmup_router_model + call_local
    "orchestrate.py",  # Slice 4: router_classifier + local_router
    "server.py",  # Slice 4: local_router warmup (no smart_router)
    "smart_router.py",  # Slice 6: deprecated re-export facade
    # M-OC8: coding pool + routing facade + tool repair + context injection
    "coding_pool_admission.py",  # NEW: eval evidence gate for IDE default pool
    "routing_facade.py",  # NEW: smart_router → routing_engine migration entry
    "routing_constants.py",  # Slice 5: ROUTE + PUBLIC_MODEL_NAME
    "tool_repair_pipeline.py",  # NEW: tool call repair pipeline
    "text_tool_extractor.py",  # NEW: text block → tool extraction
    "context_injection_trace.py",  # NEW: context injection trace endpoint
    "router_http.py",  # MODIFIED
    "router_v3.py",  # MODIFIED
    "routing_classifier.py",  # MODIFIED
    "routes/chat_support.py",  # MODIFIED: smart_router call sites
    "routes/quality_gate.py",  # MODIFIED: smart_router → backends/http_caller/cb
    "routes/agent_task_result_hooks.py",  # NEW
    "routes/admin_backends.py",  # MODIFIED: smart_router → backends
    "routes/route_registry.py",  # MODIFIED: register admin_api router
    "routes/admin_api.py",  # MODIFIED
    "routes/agent_tasks.py",  # MODIFIED
    "agent_runtime/workspace_sandbox.py",  # MODIFIED: read gate
    "code_orchestrator_context.py",  # MODIFIED
    "context_pipeline/enrich_context.py",  # MODIFIED
    "context_pipeline/processors.py",  # MODIFIED
    "lima_context.py",  # MODIFIED
    "skills_injector.py",  # MODIFIED
    "data/coding_backend_tiers.json",  # NEW: backend tier data
    "data/opencode_e2e_results.json",  # NEW: e2e results
    # Quality system: health bootstrap + probe + eval staleness
    "health_bootstrap.py",  # NEW: seed health/cb for all backends at startup
    "health_state.py",  # MODIFIED: seed_backends()
    "health_tracker.py",  # MODIFIED: re-export seed_backends
    "health_summary.py",  # MODIFIED: unknown ≠ healthy
    "probe_loop.py",  # MODIFIED: probe unknown backends in batches
    "router_circuit_breaker.py",  # MODIFIED: seed_backends()
    "server_lifespan.py",  # MODIFIED: bootstrap_runtime_health on boot
    "routes/tool_forward_stream.py",  # MODIFIED: longer tool stream read timeout
    "periodic_coding_eval.py",  # MODIFIED: run sooner when scores stale
]


def main():
    ssh = paramiko.SSHClient()
    known_hosts = os.path.expanduser("~/.ssh/known_hosts")
    if os.path.exists(known_hosts):
        try:
            ssh.load_host_keys(known_hosts)
        except Exception as exc:
            print(f"[warn] failed to load known_hosts: {exc}")
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
    else:
        print("[warn] known_hosts not found, using AutoAddPolicy")
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
    ssh.connect(SERVER, username="root", key_filename=KEY)

    sftp = ssh.open_sftp()
    for f in FILES:
        local = f"d:/QWEN3.0/{f}"
        remote = f"{REMOTE}/{f}"
        if os.path.exists(local):
            sftp.put(local, remote)
            print(f"uploaded {f}")

    sftp.close()

    # Restart via systemd only (do not fuser-kill — races with systemd unit)
    stdin, stdout, stderr = ssh.exec_command(
        "systemctl restart lima-router.service; "
        "sleep 3; "
        "for i in 1 2 3 4 5 6 7 8 9 10 11 12; do "
        "curl -sf http://127.0.0.1:8080/health >/dev/null && break; sleep 5; done; "
        "systemctl is-active lima-router.service"
    )
    active = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if active == "active":
        print("lima-router.service active")
    else:
        print(f"lima-router.service status: {active or err or 'unknown'}")
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u lima-router.service -n 25 --no-pager"
        )
        print(stdout.read().decode())

    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 8080")
    result = stdout.read().decode()
    if "8080" in result:
        print("Server UP on 8080")
    else:
        print("Port 8080 not listening")

    ssh.close()


if __name__ == "__main__":
    main()
