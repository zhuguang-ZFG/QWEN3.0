# Request Pipeline Authority (REF-005)

Date: 2026-05-25

## Decision

Production LiMa requests use **explicit integration blocks** in:

1. `server.py` / route handlers — protocol, auth, streaming bridges
2. `routing_engine.route()` — classify, select, retrieval inject, execute
3. `route_post_process.py` — post-route memory, narrative, observability

`context_pipeline.factory.build_default_pipeline()` remains a **lab and test harness**
for IDE/scenario/prompt composition experiments. It is not the single production
request pipeline.

## Rationale

- Production path already wires session memory, retrieval injection, skills, and
  observability with evidence-backed smoke tests.
- Migrating all of `server.py` to the factory pipeline would be a large blast
  radius change without immediate productivity gain.
- Lab pipeline can evolve independently; production adopts pieces only after tests
  and VPS smoke prove stability (retrieval unification in CQ-059 is the pattern).

## When to revisit

Re-evaluate factory authority when:

- `server.py` shrinks below 400 lines and route registration is fully modular
- A single request trace spans factory stages with parity tests against production
- IDE context preflight (CTX-003) needs one composable pipeline for `/v1/messages`
