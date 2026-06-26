"""Routing pipeline state graph for documentation and future LangGraph migration.

P4-6 baseline: models the 18-step request pipeline from
``docs/REQUEST_PIPELINE_AUTHORITY_CN.md`` as a directed graph and can render it
as Mermaid or a simple adjacency structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PipelineNode:
    """A single step in the routing pipeline."""

    id: str
    label: str
    group: str = ""
    notes: str = ""


@dataclass(frozen=True)
class PipelineEdge:
    """A directed transition between pipeline steps."""

    source: str
    target: str
    label: str = ""


ROUTING_PIPELINE_NODES: tuple[PipelineNode, ...] = (
    PipelineNode("identity", "身份短路", "guard", "identity_guard.detect_identity_question"),
    PipelineNode("classify", "请求分类", "classify", "routing_classifier.classify"),
    PipelineNode("scenario", "场景分类", "classify", "routing_classifier.classify_scenario"),
    PipelineNode("recall", "后端召回", "memory", "routing_engine_context.try_recall_backend"),
    PipelineNode("retrieval", "检索注入", "context", "context_pipeline.retrieval_injection"),
    PipelineNode("code_context", "代码上下文", "context", "context_pipeline.code_context_injection"),
    PipelineNode("select", "后端排序", "routing", "routing_selector.select"),
    PipelineNode("skills", "技能注入", "prompt", "skills_injector.apply_skills"),
    PipelineNode("speculative", "推测调用", "execute", "speculative.speculative_call"),
    PipelineNode("execute", "后端执行", "execute", "routing_executor.execute"),
    PipelineNode("validate", "响应验证", "quality", "response_validator.validate"),
    PipelineNode("post_process", "后处理", "quality", "routing_engine_post.post_route"),
)

ROUTING_PIPELINE_EDGES: tuple[PipelineEdge, ...] = (
    PipelineEdge("identity", "classify", "非身份问题"),
    PipelineEdge("classify", "scenario"),
    PipelineEdge("scenario", "recall"),
    PipelineEdge("recall", "retrieval"),
    PipelineEdge("retrieval", "code_context"),
    PipelineEdge("code_context", "select"),
    PipelineEdge("select", "skills"),
    PipelineEdge("skills", "speculative"),
    PipelineEdge("speculative", "execute", "复杂/未命中"),
    PipelineEdge("execute", "validate"),
    PipelineEdge("validate", "execute", "验证失败重试"),
    PipelineEdge("validate", "post_process"),
)


@dataclass
class PipelineGraph:
    """Mutable graph builder for routing pipeline visualisation."""

    nodes: dict[str, PipelineNode] = field(default_factory=dict)
    edges: list[PipelineEdge] = field(default_factory=list)

    def add_node(self, node: PipelineNode) -> "PipelineGraph":
        self.nodes[node.id] = node
        return self

    def add_edge(self, edge: PipelineEdge) -> "PipelineGraph":
        self.edges.append(edge)
        return self

    def to_mermaid(self) -> str:
        """Return a Mermaid flowchart definition."""
        lines = ["flowchart LR"]
        for node in self.nodes.values():
            safe_label = node.label.replace('"', "'")
            lines.append(f'    {node.id}["{safe_label}"]')
        for edge in self.edges:
            label = f'|"{edge.label}"|' if edge.label else ""
            lines.append(f"    {edge.source} -->{label} {edge.target}")
        return "\n".join(lines) + "\n"


def build_default_graph() -> PipelineGraph:
    """Return the graph for the current LiMa routing pipeline."""
    graph = PipelineGraph()
    for node in ROUTING_PIPELINE_NODES:
        graph.add_node(node)
    for edge in ROUTING_PIPELINE_EDGES:
        graph.add_edge(edge)
    return graph
