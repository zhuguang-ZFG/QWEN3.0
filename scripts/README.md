# LiMa operator scripts

## Active (maintained)

- `deploy_unified.py` — **默认京东云主生产**（`--target jdcloud`）；备份 `/opt/dlc-drawing/backups/`；重启 `dlc-drawing`
- `run_voice_e2e_production.py` — 语音 strict E2E（`LIMA_VOICE_E2E_STRICT=1`）
- `verify_production_deploy.py` — 生产部署验证（可含语音探针）
- `deploy_vps_bundle.py` — full post-review bundle (security + P3 + retrieval); use `--smoke`
- `cleanup_vps_backups.py` — 清理 VPS 旧备份目录（京东云默认 `/opt/dlc-drawing/backups/`）
- `deploy_prod_retrieval.py` / `vps_run_retrieval_smoke.py` — production retrieval only
- `deploy_ctx003.py` / `vps_run_messages_smoke.py` — Anthropic tool-route preflight
- `deploy_admin_paths.py` — admin portable paths
- `smoke_retrieval_trace.py` — retrieval smoke (local or VPS base URL)
- `run_ci_local.py` / `run_rag_eval_gate.py` — CI and RAG gate locally
- `smoke_online_distributions.py` — public distribution smoke

## Archive

Superseded one-off deploy and milestone probes: `scripts/archive/`.

## Hygiene

Do not commit `.db`, `.log`, `.pkl`, `.zip`, or deploy tarballs. Runtime data stays under gitignored `data/`.

**VPS deploy policy:** no on-server `runtime-before.tgz` backups. Use git tags/commits for rollback. Run `cleanup_vps_backups.py` if disk fills up.
