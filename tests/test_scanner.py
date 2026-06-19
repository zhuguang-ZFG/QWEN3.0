"""Tests for the multi-language code scanner."""

from code_context.scanner import scan_file, scan_python_file


# ---------------------------------------------------------------------------
# Scanner - multi-language dispatch
# ---------------------------------------------------------------------------


class TestScanner:
    def test_scan_python_file(self, tmp_path):
        p = tmp_path / "test.py"
        p.write_text("class Foo:\n    def bar(self): pass")
        record = scan_file(p)
        assert len(record.symbols) >= 1
        assert record.path == str(p)

    def test_scan_typescript_file(self, tmp_path):
        p = tmp_path / "app.ts"
        p.write_text("export function run(): void {}\nexport class App {}")
        record = scan_file(p)
        names = {s.name for s in record.symbols}
        assert "run" in names
        assert "App" in names

    def test_scan_unknown_extension(self, tmp_path):
        p = tmp_path / "data.xyz"
        p.write_text("hello")
        record = scan_file(p)
        assert len(record.symbols) == 0

    def test_legacy_scan_python_file(self, tmp_path):
        p = tmp_path / "old.py"
        p.write_text("def legacy(): pass")
        record = scan_python_file(p)
        assert any(s.name == "legacy" for s in record.symbols)
