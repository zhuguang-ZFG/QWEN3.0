FROM python:3.10.20-slim-bookworm@sha256:89cef4d55961e885def21b86e34e102e65b7eab8cd281e806a66ff1709c9a455 AS builder

WORKDIR /build

COPY requirements_server.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements_server.txt

# --- runtime ---
FROM python:3.10.20-slim-bookworm@sha256:89cef4d55961e885def21b86e34e102e65b7eab8cd281e806a66ff1709c9a455

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -s /bin/false -d /app lima

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

RUN chown -R lima:lima /app && chmod -R o-w /app

USER lima

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
