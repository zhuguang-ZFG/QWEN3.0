# Potpie Composio AnySearch FreeDomain Reference Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 借鉴 Potpie 的代码库理解能力、Composio 的工具网关能力、AnySearch 的实时搜索能力和 FreeDomain 的公开入口治理经验，为 LiMa 设计一个轻量、个人可控、可渐进接入的编码助手增强层。

**Architecture:** 不整体引入 Potpie、Composio、AnySearch 或 FreeDomain 的服务栈，而是提取四个可独立落地的能力：`code_context` 负责本地代码索引、相关文件召回和请求前上下文预检；`tool_gateway` 负责工具注册、凭据隔离、工具搜索和受控执行；`search_gateway` 负责显式触发的实时搜索、URL 抽取和敏感信息过滤；`ops_entrypoint` 负责域名、DNS、健康检查、证书和入口文档治理。第一阶段只做本地 SQLite/JSON 索引、本地白名单工具、搜索适配器边界和运维检查清单，不引入 Neo4j、PostgreSQL、Redis、Celery、外部 OAuth 平台、公共域名注册平台或商业多租户。

**Tech Stack:** Python 3, FastAPI, SQLite/JSON, pytest, existing LiMa `server.py`, `routing_engine.py`, `http_caller.py`, optional MCP adapter in a later phase.

---

### Source References

- Potpie repository: https://github.com/potpie-ai/potpie
  - 借鉴点：把整个 codebase 解析成 knowledge graph；以 file/class/function/import/call relationships 作为 agent grounding；提供 Codebase Q&A、Debugging、Code Generation、Spec Agent、Tool Service。
  - 不照搬点：Potpie 的完整栈包含 FastAPI、Celery、Redis、Neo4j、PostgreSQL、前端和认证，超出 LiMa 当前个人 coding assistant 后端目标。
- Composio repository: https://github.com/ComposioHQ/composio
  - 借鉴点：toolkits、tool search、context management、authentication、sandboxed workbench，让 agent 从意图变成动作。
- Composio docs: https://docs.composio.dev/docs/how-composio-works
  - 借鉴点：session/connection/tool execution 的抽象。
- Composio Single Toolkit MCP docs: https://docs.composio.dev/docs/single-toolkit-mcp
  - 借鉴点：MCP 暴露方式，但 LiMa 第一阶段只做本地轻量 adapter，不接外部平台。
- AnySearch Skill repository: https://github.com/anysearch-ai/anysearch-skill
  - 借鉴点：agent 可调用的实时搜索 skill、垂直领域搜索、批量搜索、URL 内容抽取、JSON-RPC/CLI 边界、运行时探测和可选 `ANYSEARCH_API_KEY`。
  - 不照搬点：LiMa 不让搜索默认常开，不把私有代码、token、本地路径或未脱敏错误日志发送给外部搜索服务。
- FreeDomain repository: https://github.com/DigitalPlatDev/FreeDomain
  - 借鉴点：免费域名/子域名申请平台的域名声明、审核、DNS 记录、入口归属和滥用治理思路。
  - 不照搬点：LiMa 不做公共免费域名平台注册、不接收第三方域名申请、不维护开放域名池。

### Strategic Fit For LiMa

**Potpie 对 LiMa 的价值：**

- 帮 LiMa 从“模型路由器”升级为“懂当前代码库的编码助手后端”。
- 重点借鉴 codebase indexing、symbol relationship、relevant context retrieval、spec/debug/codegen agent grounding。
- 对 `routing_engine` 本身帮助有限，但对请求前上下文预检和 IDE/Agent 体验帮助很大。

**Composio 对 LiMa 的价值：**

- 帮 LiMa 从“只转发模型请求”升级为“可控工具入口”。
- 重点借鉴 tool registry、tool search、credential isolation、execution audit、MCP compatibility。
- 不直接接 Composio Cloud，也不一次性引入 1000+ 工具。

**AnySearch 对 LiMa 的价值：**

- 帮 LiMa 补上“实时查证”和“URL 文档抽取”能力。
- 重点借鉴搜索前 domain 分类、批量搜索、URL extract、runtime 探测和 API key 优先级。
- 只在用户显式要求查最新、搜索网页、阅读 URL，或系统判断必须查证时触发；不作为普通聊天默认路径。

**FreeDomain 对 LiMa 的价值：**

- 对核心模型路由帮助很小，但对 VPS 公开入口治理有参考价值。
- 可借鉴域名归属文档、DNS 记录清单、健康检查路径、证书更新记录、滥用/误配置防护。
- 适合作为 `ops_entrypoint` 文档与检查脚本的参考，不适合作为产品功能引入。

**LiMa 约束：**

- 当前不是商业开放平台，而是个人编码助手后端。
- 优先本地可控、VPS 简化、可回滚、凭据不进 prompt。
- 任何新能力都必须先本地验证，不默认部署 VPS。

### Non-Goals

- 不整体 clone 或 vendor Potpie/Composio。
- 不引入 Neo4j、PostgreSQL、Redis、Celery 作为第一阶段硬依赖。
- 不做公共注册、商业 dashboard、billing、quota。
- 不把 GitHub、VPS、API token 注入模型上下文。
- 不允许模型自由执行任意 shell；所有工具必须白名单、参数校验、审计记录。
- 不在第一阶段做完整 MCP server，只预留 adapter 边界。
- 不建设公共免费域名服务，不接入第三方域名申请流程。
- 不把 FreeDomain 当成 LiMa 路由、上下文或工具能力的核心依赖。
- 不让所有请求默认联网搜索。
- 不把私有代码、密钥、VPS 密码、API token、完整本地路径或未脱敏错误日志发送给 AnySearch。
- 不让搜索失败影响基础 `/v1/chat/completions` 和 `/v1/messages` 可用性。

### Target Architecture

```text
IDE / Agent
    |
    v
LiMa API Compatibility Layer
    |
    +-- access_guard.py
    +-- request_context_preflight.py
    |       |
    |       +-- code_context/index_store.py
    |       +-- code_context/retriever.py
    |
    +-- routing_engine.py
    |       |
    |       +-- route_scorer.py
    |       +-- health_tracker.py
    |
    +-- tool_gateway/router.py
            |
            +-- tool_gateway/registry.py
            +-- tool_gateway/auth.py
            +-- tool_gateway/executor.py
            +-- tool_gateway/audit.py

    +-- search_gateway/
            |
            +-- search_gateway/policy.py
            +-- search_gateway/safety.py
            +-- search_gateway/anysearch_adapter.py

    +-- ops_entrypoint/
            |
            +-- domains.md
            +-- dns_check.py
            +-- public_smoke.py
```

### File Map

- Create: `docs/reference/POTPIE_COMPOSIO_ANYSEARCH_FREEDOMAIN_BORROWING_NOTES.md`
  - 记录借鉴项、拒绝项、许可/风险边界和最终取舍。
- Create: `code_context/__init__.py`
  - 模块边界，不包含业务逻辑。
- Create: `code_context/index_store.py`
  - SQLite/JSON code index 存取；第一阶段只存 file path、symbol name、kind、line、imports、mtime。
- Create: `code_context/scanner.py`
  - 本地 repo 扫描；优先 Python AST，其他文件只做路径和文本摘要。
- Create: `code_context/retriever.py`
  - 根据 query、changed files、IDE source 召回相关文件和 symbols。
- Create: `request_context_preflight.py`
  - 在进入 `routing_engine` 前构造轻量上下文补充，不改变原始用户消息。
- Create: `tool_gateway/__init__.py`
  - 模块边界。
- Create: `tool_gateway/registry.py`
  - 本地工具注册表，第一批只允许 read-only 或低风险工具。
- Create: `tool_gateway/auth.py`
  - 凭据读取与权限隔离；只从 env 或本地 ignored config 读，不返回给模型。
- Create: `tool_gateway/executor.py`
  - 白名单工具执行；拒绝任意 shell 字符串。
- Create: `tool_gateway/audit.py`
  - 记录工具调用，不记录 secret。
- Create: `search_gateway/__init__.py`
  - 模块边界，不包含业务逻辑。
- Create: `search_gateway/policy.py`
  - 判断是否需要显式实时搜索；只响应用户或系统明确要求，不作为默认聊天路径。
- Create: `search_gateway/safety.py`
  - 搜索前脱敏；移除 token、Windows 本地路径、私网 IP 等高风险片段。
- Create: `search_gateway/anysearch_adapter.py`
  - AnySearch 风格的 adapter 边界；测试中只用注入 transport，不真实联网。
- Create: `tests/test_code_context_index.py`
  - 索引与召回测试。
- Create: `tests/test_request_context_preflight.py`
  - 请求前上下文注入测试。
- Create: `tests/test_tool_gateway.py`
  - 工具注册、搜索、执行、凭据隔离测试。
- Create: `tests/test_search_gateway.py`
  - 显式搜索策略、脱敏、URL 抽取和 adapter transport 测试。
- Create: `ops_entrypoint/dns_check.py`
  - 本地 DNS/入口检查脚本；只检查 LiMa 自有域名，不做域名注册。
- Create: `ops_entrypoint/public_smoke.py`
  - 公共入口 smoke 脚本；验证 `/health`, `/v1/models`, private-auth endpoints。
- Create: `docs/OPS_ENTRYPOINTS.md`
  - LiMa 域名、FRP、VPS、证书、回滚入口记录。
- Modify later: `server.py`
  - 只在测试通过后，接入 `request_context_preflight.enhance_messages()`。
- Modify later: `docs/LIMA_MEMORY.md`, `STATUS.md`, `progress.md`
  - 记录本计划执行证据。

### Phase 0: 参考项目取舍记录

**Files:**
- Create: `docs/reference/POTPIE_COMPOSIO_ANYSEARCH_FREEDOMAIN_BORROWING_NOTES.md`

- [ ] **Step 1: 创建参考取舍文档**

写入：

```markdown
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
- Search as an explicit agent tool.
- Domain-aware search policy.
- URL extraction boundary.
- Batch search interface.
- Runtime detection and optional `ANYSEARCH_API_KEY`.

Do not borrow directly:
- Always-on web search.
- Sending private repository contents to external search.
- Logging raw search queries that may contain secrets.
- Search as a hard dependency for core chat routing.

## FreeDomain

Borrow:
- Domain ownership records.
- DNS record review workflow.
- Public endpoint smoke checklist.
- Abuse and misconfiguration guardrails.

Do not borrow directly:
- Public domain registration platform.
- Third-party domain application workflow.
- Open domain pool governance.
- Any public submission or approval UI.

## LiMa Decision

Build a small local version first:
- code_context for repo-aware prompts.
- tool_gateway for a small whitelisted local tool set.
- search_gateway for explicit realtime search and URL extraction.
- ops_entrypoint for LiMa-owned domains and VPS public smoke.
- No production deploy until local tests and manual smoke pass.
```

- [ ] **Step 2: 验证文档不包含 secret**

Run:

```powershell
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" D:\GIT\docs\reference\POTPIE_COMPOSIO_ANYSEARCH_FREEDOMAIN_BORROWING_NOTES.md
```

Expected: no output.

- [x] **Step 3: Commit**

```powershell
git -C D:\GIT add docs\reference\POTPIE_COMPOSIO_ANYSEARCH_FREEDOMAIN_BORROWING_NOTES.md
git -C D:\GIT commit -m "docs: record reference project borrowing notes"
```

### Phase 1: Potpie-Inspired Lightweight Code Context Index

**Files:**
- Create: `code_context/__init__.py`
- Create: `code_context/index_store.py`
- Create: `code_context/scanner.py`
- Test: `tests/test_code_context_index.py`

- [x] **Step 1: 写 RED 测试**

Create `tests/test_code_context_index.py`:

```python
from pathlib import Path

from code_context.scanner import scan_python_file
from code_context.index_store import CodeSymbol, InMemoryCodeIndex


def test_scan_python_file_extracts_classes_functions_and_imports(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "class Worker:\n"
        "    def run(self):\n"
        "        return Path(os.getcwd())\n\n"
        "def helper():\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )

    record = scan_python_file(target)

    assert record.path == str(target)
    assert ("os", 1) in record.imports
    assert ("pathlib.Path", 2) in record.imports
    assert CodeSymbol(name="Worker", kind="class", line=4) in record.symbols
    assert CodeSymbol(name="run", kind="function", line=5) in record.symbols
    assert CodeSymbol(name="helper", kind="function", line=8) in record.symbols


def test_in_memory_index_finds_symbols_by_query(tmp_path: Path):
    index = InMemoryCodeIndex()
    index.upsert_file(
        path="routing_engine.py",
        symbols=[CodeSymbol(name="select", kind="function", line=120)],
        imports=[],
        mtime=1.0,
    )

    matches = index.search("select backend")

    assert matches[0].path == "routing_engine.py"
    assert matches[0].symbols[0].name == "select"
```

- [x] **Step 2: 跑 RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_code_context_index.py -q --ignore=active_model
```

Expected: FAIL because `code_context` does not exist.

- [x] **Step 3: 实现最小索引结构**

Create `code_context/index_store.py`:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CodeSymbol:
    name: str
    kind: str
    line: int


@dataclass
class FileRecord:
    path: str
    symbols: list[CodeSymbol] = field(default_factory=list)
    imports: list[tuple[str, int]] = field(default_factory=list)
    mtime: float = 0.0


class InMemoryCodeIndex:
    def __init__(self) -> None:
        self._files: dict[str, FileRecord] = {}

    def upsert_file(
        self,
        path: str,
        symbols: list[CodeSymbol],
        imports: list[tuple[str, int]],
        mtime: float,
    ) -> None:
        self._files[path] = FileRecord(
            path=path,
            symbols=symbols,
            imports=imports,
            mtime=mtime,
        )

    def search(self, query: str, limit: int = 5) -> list[FileRecord]:
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[int, FileRecord]] = []
        for record in self._files.values():
            haystack = " ".join(
                [record.path]
                + [symbol.name for symbol in record.symbols]
                + [name for name, _line in record.imports]
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].path))
        return [record for _score, record in scored[:limit]]
```

Create `code_context/scanner.py`:

```python
import ast
from pathlib import Path

from .index_store import CodeSymbol, FileRecord


def scan_python_file(path: Path) -> FileRecord:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    symbols: list[CodeSymbol] = []
    imports: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(CodeSymbol(node.name, "class", node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(CodeSymbol(node.name, "function", node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imports.append((f"{node.module}.{alias.name}", node.lineno))

    return FileRecord(
        path=str(path),
        symbols=sorted(symbols, key=lambda symbol: (symbol.line, symbol.name)),
        imports=sorted(imports, key=lambda item: (item[1], item[0])),
        mtime=path.stat().st_mtime,
    )
```

- [x] **Step 4: 跑 GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_code_context_index.py -q --ignore=active_model
```

Expected: `2 passed`.

- [x] **Step 5: Commit**

```powershell
git -C D:\GIT add code_context tests\test_code_context_index.py
git -C D:\GIT commit -m "feat: add lightweight code context index"
```

### Phase 2: Request Context Preflight

**Files:**
- Create: `code_context/retriever.py`
- Create: `request_context_preflight.py`
- Test: `tests/test_request_context_preflight.py`

- [x] **Step 1: 写 RED 测试**

Create `tests/test_request_context_preflight.py`:

```python
from code_context.index_store import CodeSymbol, InMemoryCodeIndex
from request_context_preflight import enhance_messages


def test_enhance_messages_adds_relevant_file_context_without_mutating_original():
    index = InMemoryCodeIndex()
    index.upsert_file(
        path="routing_engine.py",
        symbols=[CodeSymbol(name="select", kind="function", line=120)],
        imports=[],
        mtime=1.0,
    )
    messages = [{"role": "user", "content": "why did select backend fail?"}]

    enhanced = enhance_messages(messages, index=index, max_chars=500)

    assert messages == [{"role": "user", "content": "why did select backend fail?"}]
    assert enhanced[0]["role"] == "system"
    assert "routing_engine.py" in enhanced[0]["content"]
    assert "select:function:120" in enhanced[0]["content"]
    assert enhanced[1:] == messages


def test_enhance_messages_returns_original_when_no_context_matches():
    index = InMemoryCodeIndex()
    messages = [{"role": "user", "content": "hello"}]

    enhanced = enhance_messages(messages, index=index, max_chars=500)

    assert enhanced == messages
```

- [x] **Step 2: 跑 RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_context_preflight.py -q --ignore=active_model
```

Expected: FAIL because `request_context_preflight` does not exist.

- [x] **Step 3: 实现最小 preflight**

Create `request_context_preflight.py`:

```python
from code_context.index_store import InMemoryCodeIndex


def _last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def enhance_messages(
    messages: list[dict],
    *,
    index: InMemoryCodeIndex,
    max_chars: int = 1200,
) -> list[dict]:
    query = _last_user_text(messages)
    if not query:
        return messages

    matches = index.search(query, limit=3)
    if not matches:
        return messages

    lines = ["[LiMa code context: relevant local files]"]
    for record in matches:
        symbols = ", ".join(
            f"{symbol.name}:{symbol.kind}:{symbol.line}"
            for symbol in record.symbols[:8]
        )
        lines.append(f"- {record.path} | {symbols}")

    context = "\n".join(lines)[:max_chars]
    return [{"role": "system", "content": context}] + list(messages)
```

- [x] **Step 4: 跑 GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_context_preflight.py tests\test_code_context_index.py -q --ignore=active_model
```

Expected: `4 passed`.

- [x] **Step 5: Commit**

```powershell
git -C D:\GIT add request_context_preflight.py code_context tests\test_request_context_preflight.py
git -C D:\GIT commit -m "feat: add request context preflight"
```

### Phase 3: Composio-Inspired Local Tool Gateway

**Files:**
- Create: `tool_gateway/__init__.py`
- Create: `tool_gateway/registry.py`
- Create: `tool_gateway/auth.py`
- Create: `tool_gateway/executor.py`
- Create: `tool_gateway/audit.py`
- Test: `tests/test_tool_gateway.py`

- [x] **Step 1: 写 RED 测试**

Create `tests/test_tool_gateway.py`:

```python
from tool_gateway.auth import SecretStore
from tool_gateway.executor import ToolExecutor
from tool_gateway.registry import ToolDefinition, ToolRegistry


def test_tool_registry_searches_by_intent():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="git_status",
            description="Show local git status",
            tags=("git", "repo", "status"),
            requires_secret=False,
        )
    )

    matches = registry.search("repo status")

    assert [tool.name for tool in matches] == ["git_status"]


def test_secret_store_returns_presence_without_revealing_value(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-value")
    store = SecretStore()

    assert store.has("GITHUB_TOKEN") is True
    assert store.describe("GITHUB_TOKEN") == {"name": "GITHUB_TOKEN", "configured": True}


def test_executor_rejects_unregistered_tool():
    executor = ToolExecutor(ToolRegistry())

    result = executor.execute("missing", {})

    assert result["ok"] is False
    assert result["error"] == "tool_not_registered"
```

- [x] **Step 2: 跑 RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_tool_gateway.py -q --ignore=active_model
```

Expected: FAIL because `tool_gateway` does not exist.

- [x] **Step 3: 实现本地工具注册与凭据隔离**

Create `tool_gateway/registry.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    tags: tuple[str, ...] = ()
    requires_secret: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def search(self, query: str, limit: int = 5) -> list[ToolDefinition]:
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[int, ToolDefinition]] = []
        for tool in self._tools.values():
            haystack = " ".join([tool.name, tool.description, *tool.tags]).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, tool))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [tool for _score, tool in scored[:limit]]
```

Create `tool_gateway/auth.py`:

```python
import os


class SecretStore:
    def has(self, name: str) -> bool:
        return bool(os.environ.get(name, ""))

    def get_for_executor(self, name: str) -> str:
        return os.environ.get(name, "")

    def describe(self, name: str) -> dict:
        return {"name": name, "configured": self.has(name)}
```

Create `tool_gateway/executor.py`:

```python
from .registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, name: str, args: dict) -> dict:
        tool = self._registry.get(name)
        if not tool:
            return {"ok": False, "error": "tool_not_registered"}
        return {"ok": False, "error": "executor_not_implemented", "tool": tool.name}
```

Create `tool_gateway/audit.py`:

```python
import time


def audit_event(tool: str, ok: bool, reason: str = "") -> dict:
    return {
        "time": int(time.time()),
        "tool": tool,
        "ok": ok,
        "reason": reason,
    }
```

- [x] **Step 4: 跑 GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_tool_gateway.py -q --ignore=active_model
```

Expected: `3 passed`.

- [x] **Step 5: Commit**

```powershell
git -C D:\GIT add tool_gateway tests\test_tool_gateway.py
git -C D:\GIT commit -m "feat: add local tool gateway skeleton"
```

### Phase 4: LiMa Integration Design Gate

**Files:**
- Modify: `server.py`
- Test: `tests/test_request_context_preflight.py`

- [ ] **Step 1: 不直接接入 production path，先写 integration decision**

Before modifying `server.py`, confirm all local unit tests pass:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_code_context_index.py tests\test_request_context_preflight.py tests\test_tool_gateway.py -q --ignore=active_model
```

Expected: `7 passed`.

- [ ] **Step 2: Add feature flag**

Only integrate context preflight under:

```text
LIMA_CONTEXT_PREFLIGHT=1
```

Integration rule:

- If flag is disabled, behavior must be byte-for-byte equivalent at message list boundary.
- If flag is enabled and context has matches, prepend one system message with relevant file summary.
- Never include file contents in Phase 4; only file path and symbols.
- Never include secrets or ignored files.

- [x] **Step 3: Add regression test for disabled flag**

Add to `tests/test_request_context_preflight.py`:

```python
def test_preflight_disabled_keeps_messages_unchanged(monkeypatch):
    from request_context_preflight import maybe_enhance_messages

    monkeypatch.delenv("LIMA_CONTEXT_PREFLIGHT", raising=False)
    messages = [{"role": "user", "content": "select backend"}]

    assert maybe_enhance_messages(messages, index=None) == messages
```

- [x] **Step 4: Implement `maybe_enhance_messages()`**

Add to `request_context_preflight.py`:

```python
import os


def maybe_enhance_messages(messages: list[dict], *, index) -> list[dict]:
    if os.environ.get("LIMA_CONTEXT_PREFLIGHT", "0") != "1":
        return messages
    if index is None:
        return messages
    return enhance_messages(messages, index=index)
```

- [x] **Step 5: Run tests**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_context_preflight.py -q --ignore=active_model
```

Expected: all request preflight tests pass.

### Phase 5: AnySearch-Inspired Search Gateway

**Files:**
- Create: `search_gateway/__init__.py`
- Create: `search_gateway/policy.py`
- Create: `search_gateway/safety.py`
- Create: `search_gateway/anysearch_adapter.py`
- Test: `tests/test_search_gateway.py`

- [ ] **Step 1: Write RED tests for explicit search policy, redaction, and adapter boundaries**

Create `tests/test_search_gateway.py`:

```python
from search_gateway.anysearch_adapter import AnySearchAdapter
from search_gateway.policy import should_search
from search_gateway.safety import redact_sensitive_query


def test_should_search_only_for_explicit_realtime_or_url_requests():
    assert should_search("search latest Cohere pricing") is True
    assert should_search("read https://example.com/docs") is True
    assert should_search("查一下今天的模型状态") is True
    assert should_search("why did routing_engine.select fail?") is False


def test_redact_sensitive_query_removes_tokens_paths_and_private_ips():
    fake_secret = "sk-" + "abc123456789xyz"
    query = f"error token {fake_secret} path D:\\GIT\\.env host 192.168.1.10"
    redacted = redact_sensitive_query(query)

    assert "sk-" not in redacted
    assert "D:\\GIT" not in redacted
    assert "192.168.1.10" not in redacted
    assert "[REDACTED_TOKEN]" in redacted
    assert "[REDACTED_PATH]" in redacted
    assert "[REDACTED_PRIVATE_IP]" in redacted


def test_anysearch_adapter_uses_injected_transport_with_sanitized_query():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"ok": True, "results": [{"title": "Doc", "url": "https://example.com"}]}

    adapter = AnySearchAdapter(transport=transport)
    fake_secret = "sk-" + "abc123456789xyz"
    result = adapter.search(f"latest docs token {fake_secret}", max_results=3)

    assert result["ok"] is True
    assert calls[0]["method"] == "search"
    assert calls[0]["params"]["max_results"] == 3
    assert "sk-" not in calls[0]["params"]["query"]


def test_anysearch_adapter_supports_domain_limited_batch_search():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"ok": True, "results": []}

    adapter = AnySearchAdapter(transport=transport)
    result = adapter.batch_search(
        ["latest FastAPI release", "site docs " + "sk-" + "abc123456789xyz"],
        domain="docs",
        max_results=2,
    )

    assert result == {"ok": True, "results": []}
    assert calls[0]["method"] == "batch_search"
    assert calls[0]["params"]["domain"] == "docs"
    assert calls[0]["params"]["max_results"] == 2
    assert all("sk-" not in query for query in calls[0]["params"]["queries"])


def test_anysearch_adapter_extract_url_uses_extract_method():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"ok": True, "text": "hello"}

    adapter = AnySearchAdapter(transport=transport)
    result = adapter.extract_url("https://example.com/docs")

    assert result == {"ok": True, "text": "hello"}
    assert calls[0] == {
        "method": "extract_url",
        "params": {"url": "https://example.com/docs"},
    }
```

- [ ] **Step 2: Run RED and confirm imports fail**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_search_gateway.py -q --ignore=active_model
```

Expected: FAIL because `search_gateway` does not exist.

- [x] **Step 3: Implement explicit-search policy**

Create `search_gateway/policy.py`:

```python
SEARCH_MARKERS = (
    "search",
    "latest",
    "current",
    "today",
    "web",
    "http://",
    "https://",
    "网页",
    "搜索",
    "最新",
    "查一下",
    "联网",
)


def should_search(query: str) -> bool:
    lowered = query.lower()
    return any(marker in lowered for marker in SEARCH_MARKERS)
```

- [x] **Step 4: Implement search-query redaction**

Create `search_gateway/safety.py`:

```python
import re

_TOKEN_RE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,})")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s]+")
_PRIVATE_IP_RE = re.compile(
    r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b"
)


def redact_sensitive_query(query: str) -> str:
    query = _TOKEN_RE.sub("[REDACTED_TOKEN]", query)
    query = _WIN_PATH_RE.sub("[REDACTED_PATH]", query)
    query = _PRIVATE_IP_RE.sub("[REDACTED_PRIVATE_IP]", query)
    return query
```

- [x] **Step 5: Implement AnySearch adapter with injected transport**

Create `search_gateway/anysearch_adapter.py`:

```python
from collections.abc import Callable

from .safety import redact_sensitive_query

Transport = Callable[[dict], dict]


class AnySearchAdapter:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict:
        params = {
            "query": redact_sensitive_query(query),
            "max_results": max_results,
        }
        if domain:
            params["domain"] = domain
        return self._transport({"method": "search", "params": params})

    def batch_search(
        self,
        queries: list[str],
        *,
        domain: str | None = None,
        max_results: int = 5,
    ) -> dict:
        params = {
            "queries": [redact_sensitive_query(query) for query in queries],
            "max_results": max_results,
        }
        if domain:
            params["domain"] = domain
        return self._transport({"method": "batch_search", "params": params})

    def extract_url(self, url: str) -> dict:
        return self._transport({"method": "extract_url", "params": {"url": url}})
```

Create `search_gateway/__init__.py`:

```python
"""Explicit search gateway for LiMa."""
```

- [x] **Step 6: Run GREEN for search gateway**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_search_gateway.py -q --ignore=active_model
```

Expected: `5 passed`.

- [x] **Step 7: Run focused regression with request preflight and tool gateway**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_request_context_preflight.py tests\test_tool_gateway.py tests\test_search_gateway.py -q --ignore=active_model
```

Expected: all selected tests pass.

- [x] **Step 8: Commit**

```powershell
git -C D:\GIT add search_gateway tests\test_search_gateway.py
git -C D:\GIT commit -m "feat: add explicit search gateway skeleton"
```

### Phase 6: FreeDomain-Inspired Ops Entrypoint Governance

**Files:**
- Create: `docs/OPS_ENTRYPOINTS.md`
- Create: `ops_entrypoint/__init__.py`
- Create: `ops_entrypoint/dns_check.py`
- Create: `ops_entrypoint/public_smoke.py`
- Test: `tests/test_ops_entrypoint.py`

- [x] **Step 1: 写 RED 测试**

Create `tests/test_ops_entrypoint.py`:

```python
from ops_entrypoint.dns_check import EndpointRecord, validate_endpoint_records


def test_validate_endpoint_records_requires_owned_domain_and_health_path():
    records = [
        EndpointRecord(
            name="primary",
            base_url="https://chat.donglicao.com",
            owner="lima",
            health_path="/health",
            public=True,
        )
    ]

    problems = validate_endpoint_records(records)

    assert problems == []


def test_validate_endpoint_records_rejects_missing_health_path():
    records = [
        EndpointRecord(
            name="broken",
            base_url="https://example.com",
            owner="unknown",
            health_path="",
            public=True,
        )
    ]

    problems = validate_endpoint_records(records)

    assert "broken: missing health_path" in problems
    assert "broken: owner must be lima" in problems
```

- [x] **Step 2: 跑 RED**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_ops_entrypoint.py -q --ignore=active_model
```

Expected: FAIL because `ops_entrypoint` does not exist.

- [x] **Step 3: 实现入口记录校验**

Create `ops_entrypoint/dns_check.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class EndpointRecord:
    name: str
    base_url: str
    owner: str
    health_path: str
    public: bool


def validate_endpoint_records(records: list[EndpointRecord]) -> list[str]:
    problems: list[str] = []
    for record in records:
        if record.owner != "lima":
            problems.append(f"{record.name}: owner must be lima")
        if not record.health_path:
            problems.append(f"{record.name}: missing health_path")
        if record.public and not record.base_url.startswith("https://"):
            problems.append(f"{record.name}: public endpoint must use https")
    return problems
```

Create `ops_entrypoint/public_smoke.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeTarget:
    name: str
    url: str
    requires_auth: bool = False


def default_smoke_targets(base_url: str) -> list[SmokeTarget]:
    root = base_url.rstrip("/")
    return [
        SmokeTarget("health", f"{root}/health"),
        SmokeTarget("models", f"{root}/v1/models"),
        SmokeTarget("chat", f"{root}/v1/chat/completions", requires_auth=True),
        SmokeTarget("messages", f"{root}/v1/messages", requires_auth=True),
    ]
```

- [x] **Step 4: 创建入口治理文档**

Create `docs/OPS_ENTRYPOINTS.md`:

```markdown
# LiMa Ops Entrypoints

## Purpose

Keep LiMa-owned public endpoints documented, smoke-tested, and rollback-friendly.

## Current Entrypoints

| Name | URL | Owner | Health | Auth |
|---|---|---|---|---|
| Primary API | https://chat.donglicao.com | lima | /health | private key for API calls |
| FRP health | http://47.112.162.80:8088 | lima | /health | health only |

## Rules

- Public API endpoints should use HTTPS.
- `/health` and `/v1/models` may remain public for uptime and IDE discovery.
- `/v1/chat/completions`, `/v1/messages`, `/api/live-key`, `/v1/status`, and image generation require private access.
- Record DNS, FRP, VPS, and certificate changes before deployment.
- Do not store provider credentials or VPS passwords in this document.

## FreeDomain Borrowing Boundary

Borrow the operational discipline: ownership records, DNS review, public smoke, abuse guardrails.
Do not build or join a public free-domain registration platform.
```

- [x] **Step 5: 跑 GREEN**

Run:

```powershell
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_ops_entrypoint.py -q --ignore=active_model
```

Expected: `2 passed`.

- [x] **Step 6: Commit**

```powershell
git -C D:\GIT add ops_entrypoint tests\test_ops_entrypoint.py docs\OPS_ENTRYPOINTS.md
git -C D:\GIT commit -m "feat: add ops entrypoint governance skeleton"
```

### Verification Gate

Run before claiming complete:

```powershell
git -C D:\GIT diff --check
D:\GIT\venv\Scripts\python.exe -m py_compile request_context_preflight.py code_context\index_store.py code_context\scanner.py tool_gateway\registry.py tool_gateway\auth.py tool_gateway\executor.py tool_gateway\audit.py search_gateway\policy.py search_gateway\safety.py search_gateway\anysearch_adapter.py ops_entrypoint\dns_check.py ops_entrypoint\public_smoke.py
D:\GIT\venv\Scripts\python.exe -m pytest tests\test_code_context_index.py tests\test_request_context_preflight.py tests\test_tool_gateway.py tests\test_search_gateway.py tests\test_ops_entrypoint.py -q --ignore=active_model
D:\GIT\venv\Scripts\python.exe -m pytest test_routing_engine.py test_http_caller.py test_rate_limiter.py tests\test_lima_context.py tests\test_access_guard.py tests\test_fallback_context.py tests\test_ide_detection.py -q --ignore=active_model
rg -n "sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|password\s*=|token\s*=" D:\GIT\code_context D:\GIT\tool_gateway D:\GIT\search_gateway D:\GIT\ops_entrypoint D:\GIT\request_context_preflight.py D:\GIT\docs\reference D:\GIT\docs\OPS_ENTRYPOINTS.md
```

Expected:

- `diff --check`: no whitespace errors.
- `py_compile`: no output.
- New tests pass.
- Core compatibility subset passes.
- Secret scan produces no credential values.

### Deployment Policy

- No VPS deployment in this plan by default.
- If later deploying:
  - deploy only after local tests pass;
  - backup remote runtime files first;
  - upload only touched files;
  - remote compile;
  - restart;
  - `/health`;
  - authenticated `/v1/chat/completions` smoke;
  - authenticated `/v1/messages` smoke;
  - record rollback directory.

### Risk Register

- **Context bloat:** first phase only injects paths and symbols, not full file contents.
- **Secret leakage:** scanner must skip ignored files and must not include `.env`, token files, local probe scripts, or generated logs.
- **Tool abuse:** tool gateway must default deny unregistered tools and must not execute raw shell.
- **External search privacy leak:** search gateway must redact token-like strings, Windows paths, and private IPs before calling any transport.
- **Search outage:** AnySearch adapter failures must not break `/v1/chat/completions` or `/v1/messages`; search remains explicit and optional.
- **Stale or hallucinated web results:** search output must be treated as evidence candidates, not routing truth; future integration must preserve source URLs and timestamps where available.
- **AnySearch key handling:** `ANYSEARCH_API_KEY` is optional runtime configuration and must never be written to docs, tests, logs, or prompts.
- **Operational bloat:** do not introduce Neo4j/Celery/Redis until the SQLite/JSON MVP proves useful.
- **Route regression:** context preflight must be behind `LIMA_CONTEXT_PREFLIGHT=1` until enough IDE smokes pass.
- **Domain scope creep:** FreeDomain is an ops reference only; do not expand into public domain hosting or registration.

### Success Criteria

- LiMa can answer “which files are relevant to this routing issue?” from a local index.
- LiMa can prepend a small relevant-context system block under a feature flag.
- LiMa has a local tool registry/search/executor skeleton that never exposes secrets to the prompt.
- LiMa has an explicit search decision function and redaction policy before any external search call.
- LiMa can test URL extraction, single search, and batch search through an injected adapter without real network access.
- LiMa has a documented public endpoint inventory and smoke target skeleton.
- Existing route tests still pass.
- The plan remains local-only and reversible.
