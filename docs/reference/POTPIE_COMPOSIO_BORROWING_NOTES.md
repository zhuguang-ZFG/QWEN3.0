# Potpie / Composio / AnySearch / FreeDomain Borrowing Notes

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

## AnySearch

Borrow:
- Explicit search policy before external search.
- Domain-scoped and batch search adapter boundary.
- URL extraction behind a safety guard.
- Optional API key handling with injectable transport for tests.

Do not borrow directly:
- External search as a default step for ordinary chat or code requests.
- Sending private repository paths, tokens, prompts, or local IPs to an external transport.
- A hard dependency on any single hosted search provider.

## FreeDomain

Borrow:
- Public endpoint inventory.
- Domain ownership and health-path documentation.
- Misconfiguration checks before publishing endpoints.

Do not borrow directly:
- Public domain registration workflows.
- A multi-tenant hosting product.
- Any feature that expands LiMa beyond the private coding assistant direction.

## LiMa Decision

Build a small local version first:
- code_context for repo-aware prompts.
- tool_gateway for a small whitelisted local tool set.
- search_gateway for opt-in dev search with redaction and safe URL checks.
- ops_entrypoint for endpoint inventory and public smoke checks.
- No production deploy until local tests and manual smoke pass.
