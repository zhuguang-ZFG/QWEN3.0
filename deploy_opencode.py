#!/usr/bin/env python3
"""Deploy OpenCode optimization files to VPS."""

import paramiko
import os
import time

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
    # M-OC8: coding pool + routing facade + tool repair + context injection
    "coding_pool_admission.py",  # NEW: eval evidence gate for IDE default pool
    "routing_facade.py",  # NEW: smart_router → routing_engine migration entry
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

    # Restart server — kill any process on port 8080 (uvicorn or server.py)
    stdin, stdout, stderr = ssh.exec_command(
        'fuser -k 8080/tcp 2>/dev/null; '
        'pkill -9 -f "python3.10.*server" || true; '
        'sleep 2'
    )
    stdout.read()
    time.sleep(2)

    stdin, stdout, stderr = ssh.exec_command(
        f"cd {REMOTE} && nohup /usr/local/bin/python3.10 server.py > /var/log/lima-server.log 2>&1 &"
    )
    stdout.read()
    time.sleep(8)

    # Check if server is running
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 8080")
    result = stdout.read().decode()
    if "8080" in result:
        print("Server UP on 8080")
    else:
        print("Server may not be running, checking logs...")
        stdin, stdout, stderr = ssh.exec_command("tail -20 /var/log/lima-server.log")
        print(stdout.read().decode())

    ssh.close()


if __name__ == "__main__":
    main()
