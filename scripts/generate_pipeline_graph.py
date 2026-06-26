"""Generate a Mermaid diagram of the LiMa routing pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline_graph import build_default_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Render routing pipeline graph")
    parser.add_argument(
        "--output",
        "-o",
        default="docs/assets/routing_pipeline.mmd",
        help="Output path for the Mermaid file",
    )
    args = parser.parse_args()

    graph = build_default_graph()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(graph.to_mermaid(), encoding="utf-8")
    print(f"Wrote {len(graph.nodes)} nodes / {len(graph.edges)} edges to {output}")


if __name__ == "__main__":
    main()
