"""Tests verifying long paths are not wrapped onto multiple lines in CLI output (#1291)."""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from pyrite.cli import app
from pyrite.config import KBConfig, KBType, PyriteConfig, Settings, save_config
from pyrite.models.core_types import NoteEntry
from pyrite.storage.entry_writer import create_entry_text
from pyrite.storage.repository import new_entry_text

runner = CliRunner()


def test_export_site_long_path_not_wrapped(tmp_path, monkeypatch, console_width):
    console_width(80)
    import pyrite.cli.export_commands

    monkeypatch.setattr(pyrite.cli.export_commands.console, "_width", 80)
    monkeypatch.setattr(pyrite.cli.export_commands.console, "_height", 25)

    kb_path = tmp_path / "notes_kb"
    kb_path.mkdir()
    entry_file = kb_path / "test-note.md"
    create_entry_text(
        entry_file,
        new_entry_text(NoteEntry(id="test-note", title="Test Note", body="Content")),
        root=kb_path,
    )

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = PyriteConfig(
        knowledge_bases=[KBConfig(name="notes", path=kb_path, kb_type=KBType.GENERIC)],
        settings=Settings(
            index_path=tmp_path / "index.db",
            workspace_path=tmp_path / "ws",
        ),
    )
    monkeypatch.setenv("PYRITE_CONFIG_DIR", str(config_dir))
    save_config(config)

    from pyrite.storage.database import PyriteDB
    from pyrite.storage.index import IndexManager

    db = PyriteDB(config.settings.index_path)
    IndexManager(db, config).index_all()
    db.close()

    # Create an output destination whose full absolute path is well over 100 characters
    long_dest_dir = (
        tmp_path
        / "nested_directory_structure_for_testing_path_wrapping_behavior"
        / "subfolder_level_two_to_ensure_sufficient_column_length_for_export_site"
        / "site_output"
    )

    result = runner.invoke(
        app,
        ["export", "site", "-k", "notes", "-o", str(long_dest_dir)],
    )
    assert result.exit_code == 0, result.output

    # Find the line starting with "  Output:"
    output_lines = [line for line in result.output.splitlines() if "Output:" in line]
    assert len(output_lines) == 1, result.output
    # The entire destination path must be contained on that single line
    assert str(long_dest_dir) in output_lines[0]


def test_index_sync_malformed_path_not_wrapped(tmp_path, monkeypatch, console_width):
    console_width(80)
    import pyrite.cli.index_commands

    monkeypatch.setattr(pyrite.cli.index_commands.console, "_width", 80)
    monkeypatch.setattr(pyrite.cli.index_commands.console, "_height", 25)

    kb_path = tmp_path / "notes_kb"
    nested_dir = (
        kb_path
        / "deeply_nested_directory_structure_designed_to_produce_a_very_long_path_exceeding_terminal_width"
    )
    nested_dir.mkdir(parents=True)

    malformed_file = nested_dir / "malformed_entry_file_with_bad_yaml_frontmatter.md"
    malformed_file.write_text("---\ntitle: [unclosed yaml list\n---\nBody text\n")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = PyriteConfig(
        knowledge_bases=[KBConfig(name="notes", path=kb_path, kb_type=KBType.GENERIC)],
        settings=Settings(
            index_path=tmp_path / "index.db",
            workspace_path=tmp_path / "ws",
        ),
    )
    monkeypatch.setenv("PYRITE_CONFIG_DIR", str(config_dir))
    save_config(config)

    result = runner.invoke(app, ["index", "sync"])
    assert result.exit_code == 0, result.output

    # Find bullet lines under Malformed:
    bullet_lines = [line for line in result.output.splitlines() if "•" in line]
    assert len(bullet_lines) >= 1, result.output
    # The entire path of the malformed file must appear on that single line
    assert str(malformed_file) in bullet_lines[0]
