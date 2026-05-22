# Potpie / Composio Borrowing Notes

## Potpie

Borrow:
- Codebase knowledge graph concept.
- File/class/function/import relationship indexing.
- Agent grounding through code search and graph queries.
- Spec/debug/codegen workflows grounded in repository facts.

Do not borrow directly:
- Neo4j/PostgreSQL/Redis/Celery as required first-stage dependencies.
- Full multi-user frontend/auth/product platform.
- Background job orchestration until local index MVP proves useful.

## Composio

Borrow:
- Tool registry.
- Tool search before tool execution.
- Credential isolation.
- MCP-compatible adapter boundary.
- Tool execution audit.

Do not borrow directly:
- External cloud connection manager as a core dependency.
- 1000+ tool ecosystem.
- OAuth-heavy multi-tenant flows.

## LiMa Decision

Build a small local version first:
- code_context for repo-aware prompts.
- tool_gateway for a small whitelisted local tool set.
- No production deploy until local tests and manual smoke pass.
