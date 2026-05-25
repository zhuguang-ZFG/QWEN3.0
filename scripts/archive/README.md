# Archived scripts

One-off VPS deploy, smoke, and milestone probes live here after they are superseded.
Active operators should use the maintained scripts in `scripts/`:

| Active | Purpose |
|--------|---------|
| `deploy_prod_retrieval.py` | Production retrieval stack deploy |
| `deploy_ctx003.py` | Anthropic tool-route preflight deploy |
| `deploy_admin_paths.py` | Admin path fix deploy |
| `vps_run_retrieval_smoke.py` | VPS retrieval trace smoke |
| `vps_run_messages_smoke.py` | VPS `/v1/messages` tool smoke |
| `smoke_retrieval_trace.py` | Local/public retrieval smoke |
| `run_ci_local.py` | Local CI mirror |
| `run_rag_eval_gate.py` | RAG eval gate |

Do not add new `.db`, `.log`, `.pkl`, or `.zip` files under `scripts/`; runtime data belongs in `data/` (gitignored).
