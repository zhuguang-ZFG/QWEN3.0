"""MiMo Agent mode prompts — leverage compose skills (review / verify / plan / tdd)."""

from __future__ import annotations

from dataclasses import dataclass

JSON_SUFFIX = (
    " Output a JSON array only (markdown code block ok). Fields: id, lane, severity (P0-P3), "
    "title, file, line, evidence, fix_hint, test. Omit items without evidence."
)


@dataclass(frozen=True)
class MimoMode:
    name: str
    description: str
    agent: str | None
    skill_hint: str
    focus: str


MODES: dict[str, MimoMode] = {
    "review": MimoMode(
        name="review",
        description="质量门禁：回归风险、测试缺口、边界与安全、静默降级",
        agent=None,
        skill_hint="compose review",
        focus=(
            "Use MiMo compose **review** workflow: read attached review-brief.md, "
            "use CodeGraph/grep for cross-file evidence, prioritize P0/P1 with reproducible tests."
        ),
    ),
    "verify": MimoMode(
        name="verify",
        description="修复后复验：对照上次 findings 检查 closed/still_open",
        agent=None,
        skill_hint="compose verify",
        focus=(
            "Use MiMo compose **verify** workflow: read review-brief.md and prior findings if present. "
            "Confirm fixes close prior issues; flag regressions and new P0/P1."
        ),
    ),
    "plan": MimoMode(
        name="plan",
        description="只读执行计划：分步、测试点、回滚策略（不改文件）",
        agent=None,
        skill_hint="compose plan",
        focus=(
            "Use MiMo compose **plan** workflow: read-only execution plan with steps, "
            "test commands, and rollback. Do NOT edit files."
        ),
    ),
    "security": MimoMode(
        name="security",
        description="安全边界：密钥、注入、权限、生产路径硬编码",
        agent=None,
        skill_hint="review + security lens",
        focus=(
            "Security review: secrets in repo, auth bypass, injection, unsafe defaults, "
            "production hot-path silent degradation. Evidence must cite file:line."
        ),
    ),
    "tdd": MimoMode(
        name="tdd",
        description="测试驱动：先列失败测试再最小实现建议",
        agent=None,
        skill_hint="compose tdd",
        focus=(
            "Use MiMo compose **tdd** workflow: propose failing tests first, "
            "then minimal implementation outline. JSON findings for missing test coverage."
        ),
    ),
}


def list_modes() -> list[dict[str, str]]:
    return [
        {
            "name": m.name,
            "description": m.description,
            "skill_hint": m.skill_hint,
        }
        for m in MODES.values()
    ]


def build_prompt(mode: str, task: str, *, json_output: bool = True) -> str:
    key = (mode or "review").strip().lower()
    spec = MODES.get(key) or MODES["review"]
    suffix = JSON_SUFFIX if json_output else ""
    return (
        f"[MIMO_MCP mode={spec.name} skill={spec.skill_hint}]\n"
        f"{spec.focus}\n"
        f"Task: {task}\n"
        f"Attached: review-brief.md (and scope files if any).\n"
        f"{suffix}"
    ).strip()


def resolve_agent(mode: str) -> str | None:
    key = (mode or "review").strip().lower()
    spec = MODES.get(key) or MODES["review"]
    override = __import__("os").environ.get("MIMO_MCP_AGENT", "").strip()
    if override:
        return override
    return spec.agent
