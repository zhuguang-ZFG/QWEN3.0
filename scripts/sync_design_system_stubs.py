"""Regenerate design_system.py stubs pointing to the master copy.

P1-8: 9 identical copies of ``.claude/skills/ui-ux-pro-max/scripts/design_system.py``
were scattered across agent harness directories. This script keeps the master copy
in ``.claude`` and replaces the others with tiny exec stubs, preserving both
``python design_system.py`` execution and ``import design_system`` semantics.

Run after modifying the master file or adding a new harness directory:
    python scripts/sync_design_system_stubs.py
"""

from __future__ import annotations

import pathlib

MASTER = pathlib.Path(".claude/skills/ui-ux-pro-max/scripts/design_system.py").resolve()

HARNESS_DIRS = [
    ".agent/skills/ui-ux-pro-max/scripts",
    ".codex/skills/ui-ux-pro-max/scripts",
    ".continue/skills/ui-ux-pro-max/scripts",
    ".cursor/skills/ui-ux-pro-max/scripts",
    ".github/prompts/ui-ux-pro-max/scripts",
    ".qoder/skills/ui-ux-pro-max/scripts",
    ".roo/skills/ui-ux-pro-max/scripts",
    ".trae/skills/ui-ux-pro-max/scripts",
]

STUB = '''\
"""Auto-generated stub: loads the master design_system.py.

Master: .claude/skills/ui-ux-pro-max/scripts/design_system.py
Regenerate: python scripts/sync_design_system_stubs.py
"""

from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_MASTER = (_HERE / "../../../../.claude/skills/ui-ux-pro-max/scripts/design_system.py").resolve()

if not _MASTER.exists():
    raise FileNotFoundError(f"Master design_system.py not found: {_MASTER}")

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_globals = globals()
_globals["__file__"] = str(_MASTER)
_globals["__name__"] = __name__
exec(compile(_MASTER.read_text(encoding="utf-8"), str(_MASTER), "exec"), _globals)
'''


def main() -> None:
    if not MASTER.exists():
        raise SystemExit(f"Master file missing: {MASTER}")

    for rel in HARNESS_DIRS:
        dest = pathlib.Path(rel) / "design_system.py"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(STUB, encoding="utf-8")
        print(f"[sync] {dest}")

    print(f"[sync] master: {MASTER}")


if __name__ == "__main__":
    main()
