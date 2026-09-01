FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS builder

WORKDIR /build

COPY requirements_server.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements_server.txt

# --- runtime ---
FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -s /bin/false -d /app lima

COPY --from=builder /install /usr/local

WORKDIR /app
# CNT-01: copy only production runtime trees (not full workspace dump)
COPY server_dlc.py access_guard.py runtime_env.py rate_limiter.py async_utils.py \
     app_status_ws_connections.py app_status_ws_ticket.py voice_app_ws_ticket.py \
     voice_ws_connections.py ws_ticket.py device_protocol_registry.py \
     dashscope_image_client.py requirements_server.txt ./
COPY routes/ routes/
COPY device_gateway/ device_gateway/
COPY device_ledger/ device_ledger/
COPY device_memory/ device_memory/
COPY device_intelligence/ device_intelligence/
COPY device_logic/ device_logic/
COPY device_policy/ device_policy/
COPY device_workflow/ device_workflow/
COPY device_voice/ device_voice/
COPY device_artifacts/ device_artifacts/
COPY dlc_api/ dlc_api/
COPY dlc_core/ dlc_core/
COPY dlc_mcp/ dlc_mcp/
COPY integrations/ integrations/
COPY observability/ observability/
COPY xiaozhi_drawing/ xiaozhi_drawing/
COPY config/ config/
COPY common/ common/
COPY client_keys/ client_keys/

RUN chown -R lima:lima /app && chmod -R o-w /app

USER lima

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

CMD ["python", "-m", "uvicorn", "server_dlc:app", "--host", "0.0.0.0", "--port", "8081"]
