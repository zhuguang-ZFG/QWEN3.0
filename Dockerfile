FROM python:3.10-slim AS builder

WORKDIR /build

COPY requirements_server.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements_server.txt

# --- runtime ---
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
