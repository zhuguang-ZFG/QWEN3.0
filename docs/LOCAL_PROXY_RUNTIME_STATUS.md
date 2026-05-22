# Local Proxy Runtime Status

Date: 2026-05-22

## Conclusion

The Kimi and SCNet-large services are local Windows proxy services under `D:\ollama_server`, not VPS-local services.

Checking `localhost:4504` or `localhost:4505` on the VPS is the wrong health signal unless those ports are explicitly exposed through a tunnel. On this machine, both ports are listening:

- `4504`: `node D:\ollama_server\kimi_proxy.js`
- `4505`: `node D:\ollama_server\scnet_large_proxy.js`

## Current Routing Shape

- `D:\GIT\backends.py` points Kimi and SCNet-large backends at `http://localhost:4504` and `http://localhost:4505`.
- That works only when the LiMa router process itself runs on this Windows machine.
- `D:\GIT\frp\frpc.toml` exposes local `8080` as VPS `8088`.
- Therefore the intended closed loop is: IDE/public URL -> VPS `8088` -> FRP -> Windows `8080` -> LiMa router -> Windows `4504/4505`.

## Problems Found

- `D:\GIT\local_router_start.bat` pointed to missing `D:\GIT\local_router.py`.
- The same script displayed stale ports `8090 -> 9090`, while FRP actually maps `8080 -> 8088`.
- No local process was listening on `8080`, so the FRP API route had no local target.
- `D:\ollama_server\lima-health.bat` did not monitor Kimi `4504`, SCNet-large `4505`, LiMa API `8080`, or `frpc.exe`.

## Fix Applied

- `local_router_start.bat` now starts `D:\GIT\server.py` on port `8080`.
- The startup script no longer blocks on `pause` when launched by Task Scheduler.
- `lima-health.bat` now checks and restarts:
  - Kimi proxy `4504`
  - SCNet-large proxy `4505`
  - LiMa API router `8080`
  - FRP tunnel process

## Verification Notes

- `http://127.0.0.1:4504/v1/models` returns Kimi models.
- `http://127.0.0.1:4505/v1/models` returns SCNet-large models.
- `http://127.0.0.1:4505/v1/chat/completions` returns a valid OpenAI-compatible response.
- `http://127.0.0.1:8080/health` returns `{"status":"ok","version":"2.0","model":"lima-1.3"}` after the fixed startup path.
- A realistic local IDE-style request to `http://127.0.0.1:8080/v1/chat/completions` returned HTTP 200 through `scnet_ds_pro`.
- A fresh local IDE-style request later returned HTTP 200 through `cf_qwen_coder`, confirming non-cache route execution.
- `frpc.exe` registers `redcode-api` successfully. After opening VPS `8088/tcp` in `firewalld`, `http://47.112.162.80:8088/health`, `/v1/models`, and `/v1/chat/completions` all return HTTP 200 through the FRP path.
- Kimi chat is not currently usable: the proxy is running, but `/v1/chat/completions` returns `chat.anonymous_usage_exceeded`, so the Kimi session needs re-login/refresh.
