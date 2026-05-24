# esp32S_XYZ Optimization Roadmap

> Updated: 2026-05-24

## Mandate

LiMa is authorized to perform deep optimization of
`https://github.com/zhuguang-ZFG/esp32S_XYZ.git`. When the evidence supports it,
LiMa may refactor the product repository itself, not only the main LiMa backend.

The local working clone is:

```text
D:\GIT\esp32S_XYZ
```

The main LiMa repository tracks that clone through the `esp32S_XYZ` submodule.

## Operating Rules

1. Product-repo changes happen inside `D:\GIT\esp32S_XYZ` and are committed to
   `zhuguang-ZFG/esp32S_XYZ.git`.
2. Main-repo changes happen inside `D:\GIT` and are committed to
   `zhuguang-ZFG/QWEN3.0.git`.
3. Cross-repo work should land in this order:
   - update and verify `esp32S_XYZ`;
   - push `esp32S_XYZ`;
   - update the main LiMa submodule pointer and any LiMa backend/docs/tests;
   - push the main LiMa branch.
4. Refactors are allowed when they improve testability, reliability, safety,
   hardware-release evidence, or LiMa backend integration.
5. Do not rewrite product history, rotate secrets, deploy to VPS, run hardware
   destructive actions, or change production OTA/provisioning behavior without
   an explicit release gate.

## First Optimization Pass

The first deep pass should be evidence-first:

| Phase | Goal | Output |
|---|---|---|
| 0 | Reproduce the current product baseline | Local CI-equivalent command log and known gaps |
| 1 | Map LiMa backend contracts used by the product | Contract table for AI, voice, image/vector, safety, OTA, telemetry, and task orchestration |
| 2 | Identify high-value refactor targets | Ranked findings with affected files, risk, tests, and expected benefit |
| 3 | Implement low-risk consolidation | Small commits that preserve behavior and improve verification |
| 4 | Add LiMa integration adapters where needed | Product-side adapter(s), main-repo endpoint/tests, and smoke evidence |
| 5 | Prepare hardware-gated release evidence | Checklist for real U1/U8 device, OTA, provisioning, motion, voice, and monitoring validation |

Direct U8-to-LiMa work is tracked separately in
`docs/superpowers/plans/2026-05-24-lima-direct-device-gateway.md`.
Xiaozhi server runtime retirement is tracked in
`docs/superpowers/plans/2026-05-24-xiaozhi-server-deprecation-removal.md`.

## Likely Focus Areas

- Manager API service complexity around tasks, safety, voiceprint, OTA, and
  content/image/vector flows.
- Xiaozhi server bridges that should call LiMa-hosted AI capabilities instead
  of product-local provider logic.
- Edge-A/B/C/D schemas and examples as the stable device/backend contract.
- Fake U1/device/AI tools as a pre-hardware verification harness.
- Monitoring and runbooks for product-facing LiMa backend endpoints.
- Secret hygiene, especially provider keys, device secrets, OTA signing keys,
  and VPS deployment credentials.

## Verification Baseline

Before claiming a product refactor is complete, run the narrow checks that
cover the touched area and record the result in both repositories when the work
is cross-repo.

Minimum product-side starting point:

```powershell
cd D:\GIT\esp32S_XYZ
python tools/validate_schemas.py
python tools/check_gpio.py
python -m unittest discover -s tests -p "test_*.py" -v
```

Main LiMa checks depend on the touched backend contract. For endpoint or model
routing changes, include the relevant pytest target suite and public/private
smoke evidence before updating the submodule pointer.
