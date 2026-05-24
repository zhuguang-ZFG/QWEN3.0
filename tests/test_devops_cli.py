"""Tests for M11 deployment inventory, CLI status, and edit protocol."""

import json

import pytest

from cli_status import (
    StatusRow,
    StatusTable,
    collect_all_status,
    collect_router_status,
    format_status_json,
    format_status_text,
    print_status,
)
from deployment.inventory import (
    DeploymentInventory,
    ServiceEntry,
    build_inventory,
    format_inventory_markdown,
)
from edit_protocol import (
    EditBlock,
    EditResult,
    apply_edit_block,
    apply_edits,
    format_edit_block,
    parse_edit_blocks,
)

SEARCH_MARKER = "<" * 7 + " SEARCH"
REPLACE_MARKER = ">" * 7 + " REPLACE"


# Deployment inventory

def test_build_inventory_has_services():
    inv = build_inventory()
    assert len(inv.services) >= 3
    names = {service.name for service in inv.services}
    assert "lima-router" in names
    assert "nginx-https" in names


def test_inventory_has_smoke_commands():
    inv = build_inventory()
    assert len(inv.smoke_commands) >= 1
    assert any("health" in command for command in inv.smoke_commands)


def test_inventory_smoke_commands_do_not_hardcode_bearer_secret():
    inv = build_inventory()
    joined = "\n".join(inv.smoke_commands)
    assert "Bearer lima-local" not in joined
    assert "Bearer $LIMA_API_KEY" in joined


def test_inventory_has_rollback_steps():
    inv = build_inventory()
    assert len(inv.rollback_steps) >= 2
    assert any("backup" in step for step in inv.rollback_steps)


def test_format_inventory_markdown():
    inv = build_inventory()
    md = format_inventory_markdown(inv)
    assert "## LiMa Deployment Inventory" in md
    assert "lima-router" in md
    assert "Rollback" in md
    assert "Smoke" in md


def test_inventory_dataclasses_are_exported():
    inv = DeploymentInventory(services=[ServiceEntry(name="svc", port=1, description="d")])
    assert inv.services[0].name == "svc"


# CLI status

def test_status_row_and_table():
    row = StatusRow(name="test", value="42", status="ok", detail="all good")
    assert row.name == "test"
    table = StatusTable(title="Unit", rows=[row])
    assert table.title == "Unit"


def test_status_row_normalizes_unknown_status():
    row = StatusRow(name="test", value="42", status="strange")
    assert row.status == "warn"
    text = format_status_text([StatusTable(title="T", rows=[row])])
    assert "! " in text


def test_status_row_redacts_secret_like_values():
    row = StatusRow(
        name="provider",
        value="api_key=sk-abcdefghij12345678901234567890",
        detail="Bearer abcdefghijklmnopqrstuvwxyz123456",
    )
    payload = row.to_dict()
    dumped = json.dumps(payload)
    assert "sk-abcdefghij" not in dumped
    assert "abcdefghijklmnopqrstuvwxyz123456" not in dumped
    assert "[REDACTED]" in dumped


def test_format_status_text():
    table = StatusTable(title="Test", rows=[
        StatusRow(name="uptime", value="3600s", status="ok"),
        StatusRow(name="errors", value="3", status="warn", detail="rate_limited"),
    ])
    text = format_status_text([table])
    assert "Test" in text
    assert "uptime" in text
    assert "3600s" in text


def test_format_status_json():
    table = StatusTable(title="Test", rows=[
        StatusRow(name="key", value="val", status="ok"),
    ])
    data = json.loads(format_status_json([table]))
    assert "Test" in data
    assert data["Test"][0]["name"] == "key"


def test_collect_router_status():
    table = collect_router_status()
    assert table.title == "Router"
    assert len(table.rows) >= 1


def test_collect_all_status():
    tables = collect_all_status()
    assert len(tables) >= 1
    assert any(table.title == "Router" for table in tables)


def test_print_status_text():
    text = print_status("text")
    assert "Router" in text


def test_print_status_json():
    data = json.loads(print_status("json"))
    assert "Router" in data


# Edit protocol

def test_format_edit_block():
    block = format_edit_block("test.py", "old_func()", "new_func()", reason="rename")
    assert SEARCH_MARKER in block
    assert "=======" in block
    assert REPLACE_MARKER in block
    assert "File: test.py" in block
    assert "old_func()" in block
    assert "new_func()" in block


def test_parse_single_edit_block():
    text = "\n".join([
        "# File: test.py",
        SEARCH_MARKER,
        "hello world",
        "=======",
        "goodbye world",
        REPLACE_MARKER,
    ])
    blocks = parse_edit_blocks(text, default_file="unknown.py")
    assert len(blocks) == 1
    assert blocks[0].file_path == "test.py"
    assert blocks[0].search == "hello world"
    assert blocks[0].replace == "goodbye world"


def test_parse_multiple_edit_blocks():
    text = "\n".join([
        SEARCH_MARKER,
        "foo",
        "=======",
        "bar",
        REPLACE_MARKER,
        "",
        "some text",
        "",
        SEARCH_MARKER,
        "baz",
        "=======",
        "qux",
        REPLACE_MARKER,
    ])
    blocks = parse_edit_blocks(text, default_file="file.py")
    assert len(blocks) == 2


def test_parse_edit_blocks_default_file():
    text = "\n".join([
        SEARCH_MARKER,
        "x",
        "=======",
        "y",
        REPLACE_MARKER,
    ])
    blocks = parse_edit_blocks(text, default_file="default.py")
    assert blocks[0].file_path == "default.py"


def test_apply_edit_block_success():
    content = "def hello():\n    return 'world'\n"
    block = EditBlock(file_path="test.py", search="return 'world'", replace="return 'earth'")
    result = apply_edit_block(content, block)
    assert result.ok is True
    assert result.applied is True
    assert "earth" in result.preview
    assert result.file_path == "test.py"


def test_apply_edit_block_not_found():
    content = "hello"
    block = EditBlock(file_path="x.py", search="nonexistent", replace="x")
    result = apply_edit_block(content, block)
    assert result.ok is False
    assert "not found" in result.error


def test_apply_edit_block_non_unique():
    content = "x = 1\ny = 1\nx = 1\n"
    block = EditBlock(file_path="x.py", search="x = 1", replace="x = 2")
    result = apply_edit_block(content, block)
    assert result.ok is False
    assert "matches" in result.error


def test_apply_edits_sequential():
    content = "line1\nline2\nline3\n"
    blocks = [
        EditBlock(file_path="f", search="line1", replace="LINE1"),
        EditBlock(file_path="f", search="line3", replace="LINE3"),
    ]
    result = apply_edits(content, blocks)
    assert "LINE1" in result
    assert "LINE3" in result
    assert "line2" in result  # unchanged


def test_apply_edits_raises_on_missing_block():
    with pytest.raises(ValueError, match="not found"):
        apply_edits("hello", [EditBlock(file_path="x.py", search="missing", replace="x")])


def test_apply_edits_raises_on_non_unique_block():
    with pytest.raises(ValueError, match="matches 2 times"):
        apply_edits("x\nx\n", [EditBlock(file_path="x.py", search="x", replace="y")])


def test_parse_edit_blocks_empty():
    assert parse_edit_blocks("just some text") == []


def test_edit_block_dataclass():
    block = EditBlock(file_path="a.py", search="s", replace="r", reason="test")
    assert block.file_path == "a.py"
    assert block.reason == "test"


def test_edit_result_dataclass():
    result = EditResult(ok=True, file_path="a.py", applied=True, preview="+ new")
    assert result.ok is True
    assert result.preview == "+ new"
