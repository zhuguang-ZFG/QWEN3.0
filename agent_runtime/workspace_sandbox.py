"""Workspace write sandbox with bounded directory, patch preview, and rollback."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


SANDBOX_ROOT_DEFAULT = ".lima-sandbox"


@dataclass
class PatchRecord:
    file_path: str
    original: str = ""
    patched: str = ""
    diff_preview: str = ""
    applied: bool = False
    audit_ref: str = ""


@dataclass
class WriteResult:
    ok: bool
    files_changed: int = 0
    patches: list[PatchRecord] = field(default_factory=list)
    error: str = ""
    dry_run: bool = True


class ReadTracker:
    """Tracks files read before allowing SEARCH/replace edits (MiMo-style gate)."""

    def __init__(self) -> None:
        self._read_paths: set[str] = set()

    def record_read(self, file_path: str) -> None:
        normalized = file_path.replace("\\", "/").lstrip("./")
        if normalized:
            self._read_paths.add(normalized)

    def has_read(self, file_path: str) -> bool:
        normalized = file_path.replace("\\", "/").lstrip("./")
        return normalized in self._read_paths

    def clear(self) -> None:
        self._read_paths.clear()


class WorkspaceSandbox:
    """Constrained write sandbox. All writes stay under a bounded root."""

    def __init__(
        self,
        root: str = "",
        dry_run: bool = True,
        *,
        read_tracker: ReadTracker | None = None,
        enforce_read_gate: bool | None = None,
    ) -> None:
        self.root = os.path.abspath(root or SANDBOX_ROOT_DEFAULT)
        self.dry_run = dry_run
        self.read_tracker = read_tracker or ReadTracker()
        if enforce_read_gate is None:
            enforce_read_gate = os.environ.get(
                "LIMA_WORKSPACE_READ_GATE", "0"
            ).strip().lower() in {"1", "true", "yes"}
        self.enforce_read_gate = enforce_read_gate
        self._patches: list[PatchRecord] = []

    def record_read(self, file_path: str) -> None:
        self.read_tracker.record_read(file_path)

    def apply_patches(self, patches: list[PatchRecord]) -> WriteResult:
        if not self._validate_root():
            return WriteResult(ok=False, error="sandbox root not accessible")

        batch: list[PatchRecord] = []
        for patch in patches:
            target = self._resolve_target(patch.file_path)
            if target is None:
                return WriteResult(ok=False, error="patch path escapes sandbox")

            gate_err = self._validate_edit_gate(patch, target)
            if gate_err:
                return WriteResult(ok=False, error=gate_err)

            patch.audit_ref = f"write-audit-{int(time.time())}"
            if self.dry_run:
                patch.diff_preview = self._compute_diff(patch.original, patch.patched)
            else:
                patch.applied = self._write_file(patch)
            batch.append(patch)
            self._patches.append(patch)

        self._audit_patches(batch)
        return WriteResult(
            ok=self.dry_run or all(p.applied for p in batch),
            files_changed=len(batch),
            patches=list(batch),
            dry_run=self.dry_run,
        )

    def preview(self, patches: list[PatchRecord]) -> list[str]:
        return [self._compute_diff(p.original, p.patched) for p in patches]

    def rollback(self, patch: PatchRecord) -> bool:
        if not patch.applied:
            return False
        target = self._resolve_target(patch.file_path)
        if target is None:
            return False
        try:
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(patch.original)
            self._audit_rollback(patch)
            return True
        except OSError:
            return False

    def _validate_root(self) -> bool:
        return os.path.isdir(os.path.dirname(self.root) or ".")

    def _write_file(self, patch: PatchRecord) -> bool:
        target = self._resolve_target(patch.file_path)
        if target is None:
            return False
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(patch.patched)
            self._record_git_diff(patch.file_path)
            return True
        except OSError:
            return False

    def _record_git_diff(self, file_path: str) -> None:
        """Run git diff to record what changed after a write."""
        try:
            import subprocess
            target = self._resolve_target(file_path)
            if target is None:
                return
            result = subprocess.run(
                ["git", "diff", "--no-index", "--", file_path],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.path.dirname(self.root) or ".",
            )
            diff_output = (result.stdout or "")[:2048]
            if diff_output:
                _log.info("workspace_git_diff file=%s lines=%d", file_path, diff_output.count("\n"))
                try:
                    from agent_runtime.audit_trail import audit_event
                    audit_event(
                        "workspace_git_diff",
                        detail=f"file={file_path} diff_lines={diff_output.count(chr(10))}",
                    )
                except Exception:
                    _log.debug("workspace_sandbox: audit event failed", exc_info=True)
        except Exception as exc:
            _log.debug("workspace git diff skipped: %s", type(exc).__name__)

    def _compute_diff(self, original: str, patched: str) -> str:
        added = set(patched.splitlines()) - set(original.splitlines())
        removed = set(original.splitlines()) - set(patched.splitlines())
        lines = []
        for line in removed:
            lines.append(f"- {line[:80]}")
        for line in added:
            lines.append(f"+ {line[:80]}")
        return "\n".join(lines[:20])

    def _audit_patches(self, patches: list[PatchRecord]) -> None:
        try:
            from agent_runtime.audit_trail import audit_event

            for patch in patches:
                audit_event(
                    "workspace_patch",
                    detail=(
                        f"file={patch.file_path} applied={patch.applied} "
                        f"dry_run={self.dry_run}"
                    ),
                )
        except Exception as exc:
            _log.debug("workspace patch audit skipped: %s", type(exc).__name__)

    def _audit_rollback(self, patch: PatchRecord) -> None:
        try:
            from agent_runtime.audit_trail import audit_event

            audit_event("workspace_rollback", detail=f"file={patch.file_path}")
        except Exception as exc:
            _log.debug("workspace rollback audit skipped: %s", type(exc).__name__)

    def _validate_edit_gate(self, patch: PatchRecord, target: str) -> str | None:
        """Require prior read + byte-exact SEARCH block when editing existing files."""
        is_new_file = not os.path.isfile(target)
        if is_new_file:
            return None
        if self.enforce_read_gate and not self.read_tracker.has_read(patch.file_path):
            return f"edit blocked: file not read yet: {patch.file_path}"
        if patch.original:
            try:
                on_disk = open(target, encoding="utf-8").read()
            except OSError:
                return f"cannot read file for SEARCH validation: {patch.file_path}"
            if patch.original not in on_disk:
                return (
                    f"SEARCH block not found in {patch.file_path} "
                    "(byte-exact match required)"
                )
        return None

    def _resolve_target(self, file_path: str) -> str | None:
        target = os.path.abspath(os.path.join(self.root, file_path))
        return target if self._is_inside_root(target) else None

    def _is_inside_root(self, path: str) -> bool:
        try:
            return os.path.commonpath([self.root, path]) == self.root
        except ValueError:
            return False
