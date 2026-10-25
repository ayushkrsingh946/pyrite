"""Regression tests for software-kb CLI ID preservation (#1293).

Verifies that:
- sw backlog (flat and grouped), sw epics, sw epic, and sw adrs tables
  preserve full IDs without slicing or truncation, even with COLUMNS=80.
- sw components JSON rows include "id" and "kb_name".
- sw components Rich table renders an ID column without cutting the id.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

import pyrite.cli
from pyrite.config import KBConfig, PyriteConfig, Settings
from pyrite.storage.database import PyriteDB

# Must import pyrite.cli before software-kb cli to ensure plugin loading order (#900)
cli = importlib.import_module("pyrite_software_kb.cli") if pyrite.cli else None


def _make_test_env(tmp_path: Path, entries: list[dict], links: list[dict] | None = None):
    db_path = tmp_path / "test.db"
    db = PyriteDB(db_path)
    db._raw_conn.execute(
        "INSERT INTO kb (name, path, kb_type) VALUES (?, ?, ?)",
        ("test", str(tmp_path), "software"),
    )
    for e in entries:
        meta = e.get("metadata", {})
        db._raw_conn.execute(
            "INSERT INTO entry (id, kb_name, entry_type, title, body, status, priority, assignee, metadata, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                e["id"],
                e.get("kb_name", "test"),
                e["entry_type"],
                e.get("title", e["id"]),
                e.get("body", ""),
                e.get("status"),
                e.get("priority"),
                e.get("assignee"),
                json.dumps(meta),
                e.get("created_at", "2026-01-01T00:00:00"),
                e.get("updated_at", "2026-01-01T00:00:00"),
            ),
        )
    for lnk in links or []:
        db._raw_conn.execute(
            "INSERT INTO link (source_id, source_kb, target_id, target_kb, relation, inverse_relation) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                lnk["source_id"],
                lnk.get("source_kb", "test"),
                lnk["target_id"],
                lnk.get("target_kb", "test"),
                lnk["relation"],
                lnk["inverse_relation"],
            ),
        )
    db._raw_conn.commit()
    db.close()

    config = PyriteConfig(
        knowledge_bases=[KBConfig(name="test", path=tmp_path, kb_type="software")],
        settings=Settings(index_path=db_path),
    )
    return config


def _invoke_sw(config: PyriteConfig, args: list[str], columns: int = 80):
    runner = CliRunner()
    env = {"COLUMNS": str(columns), "TERM": "xterm-256color"}
    with (
        patch("pyrite.config.load_config", return_value=config),
        patch("pyrite_software_kb.cli.load_config", return_value=config),
        patch("pyrite.cli.context.load_config", return_value=config),
    ):
        return runner.invoke(cli.sw_app, args, env=env)


def test_sw_backlog_rich_preserves_30_char_id_at_80_columns(tmp_path: Path):
    item_id = "login-endpoint-auth-service-30"  # 30 chars
    assert len(item_id) == 30
    config = _make_test_env(
        tmp_path,
        [
            {
                "id": item_id,
                "entry_type": "backlog_item",
                "title": "Login endpoint implementation",
                "status": "accepted",
                "priority": "high",
                "metadata": {"kind": "feature", "status": "accepted", "priority": "high"},
            }
        ],
    )

    result = _invoke_sw(config, ["backlog", "-k", "test", "--format", "rich"], columns=80)
    assert result.exit_code == 0, result.output
    # Must contain the entire ID whole without truncation or ellipsis
    assert item_id in result.output
    # The whole ID must be printed on a single line
    lines_with_id = [line for line in result.output.splitlines() if item_id in line]
    assert len(lines_with_id) == 1


def test_sw_backlog_grouped_rich_preserves_30_char_id_at_80_columns(tmp_path: Path):
    epic_id = "user-auth-epic-identifier-long"
    item_id = "order-processing-queue-item-30"
    config = _make_test_env(
        tmp_path,
        [
            {
                "id": epic_id,
                "entry_type": "backlog_item",
                "title": "User Auth Epic",
                "status": "in_progress",
                "priority": "high",
                "metadata": {"kind": "epic"},
            },
            {
                "id": item_id,
                "entry_type": "backlog_item",
                "title": "Order processing queue",
                "status": "planned",
                "priority": "medium",
                "metadata": {"kind": "feature"},
            },
        ],
        links=[
            {
                "source_id": epic_id,
                "target_id": item_id,
                "relation": "has_subtask",
                "inverse_relation": "subtask_of",
            }
        ],
    )

    result = _invoke_sw(
        config,
        ["backlog", "-k", "test", "--group-by", "epic", "--format", "rich"],
        columns=80,
    )
    assert result.exit_code == 0, result.output
    assert item_id in result.output
    lines_with_id = [line for line in result.output.splitlines() if item_id in line]
    assert len(lines_with_id) == 1


def test_sw_epics_rich_preserves_30_char_id_at_80_columns(tmp_path: Path):
    epic_id = "epic-notification-pipeline-030"
    assert len(epic_id) == 30
    config = _make_test_env(
        tmp_path,
        [
            {
                "id": epic_id,
                "entry_type": "backlog_item",
                "title": "Notification Pipeline Epic",
                "status": "in_progress",
                "priority": "high",
                "metadata": {"kind": "epic"},
            }
        ],
    )

    result = _invoke_sw(config, ["epics", "-k", "test", "--format", "rich"], columns=80)
    assert result.exit_code == 0, result.output
    assert epic_id in result.output
    lines_with_id = [line for line in result.output.splitlines() if epic_id in line]
    assert len(lines_with_id) == 1


def test_sw_epic_detail_rich_preserves_30_char_id(tmp_path: Path):
    epic_id = "epic-database-migration-pipeline"
    item_id = "subtask-schema-migration-v2-30"
    assert len(item_id) == 30
    config = _make_test_env(
        tmp_path,
        [
            {
                "id": epic_id,
                "entry_type": "backlog_item",
                "title": "Database Migration",
                "status": "in_progress",
                "priority": "high",
                "metadata": {"kind": "epic"},
            },
            {
                "id": item_id,
                "entry_type": "backlog_item",
                "title": "Run schema migration script",
                "status": "in_progress",
                "priority": "high",
                "metadata": {"kind": "feature"},
            },
        ],
        links=[
            {
                "source_id": epic_id,
                "target_id": item_id,
                "relation": "has_subtask",
                "inverse_relation": "subtask_of",
            }
        ],
    )

    result = _invoke_sw(config, ["epic", epic_id, "-k", "test", "--format", "rich"], columns=80)
    assert result.exit_code == 0, result.output
    assert item_id in result.output


def test_sw_adrs_rich_preserves_long_id_at_80_columns(tmp_path: Path):
    adr_id = "adr-distributed-event-bus-v2-30"
    assert len(adr_id) >= 30
    config = _make_test_env(
        tmp_path,
        [
            {
                "id": adr_id,
                "entry_type": "adr",
                "title": "Adopt Event Bus",
                "status": "accepted",
                "metadata": {"adr_number": 1, "status": "accepted"},
            }
        ],
    )

    result = _invoke_sw(config, ["adrs", "-k", "test", "--format", "rich"], columns=80)
    assert result.exit_code == 0, result.output
    assert adr_id in result.output
    lines_with_id = [line for line in result.output.splitlines() if adr_id in line]
    assert len(lines_with_id) == 1


def test_sw_components_json_has_id_and_kb_name(tmp_path: Path):
    comp_id = "api-gateway-service-component-30"
    config = _make_test_env(
        tmp_path,
        [
            {
                "id": comp_id,
                "kb_name": "test",
                "entry_type": "component",
                "title": "Api gateway",
                "metadata": {"kind": "service", "path": "services/gateway", "owner": "platform"},
            }
        ],
    )

    result = _invoke_sw(config, ["components", "-k", "test", "--format", "json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == comp_id
    assert row["kb_name"] == "test"
    assert row["title"] == "Api gateway"
    assert row["kind"] == "service"
    assert row["path"] == "services/gateway"
    assert row["owner"] == "platform"


def test_sw_components_rich_has_id_column_and_shows_id(tmp_path: Path):
    comp_id = "api-gateway-service-component-30"
    config = _make_test_env(
        tmp_path,
        [
            {
                "id": comp_id,
                "kb_name": "test",
                "entry_type": "component",
                "title": "Api gateway",
                "metadata": {"kind": "service", "path": "services/gateway", "owner": "platform"},
            }
        ],
    )

    result = _invoke_sw(config, ["components", "-k", "test", "--format", "rich"], columns=80)
    assert result.exit_code == 0, result.output
    assert "ID" in result.output
    assert comp_id in result.output
    lines_with_id = [line for line in result.output.splitlines() if comp_id in line]
    assert len(lines_with_id) == 1


def test_sw_empty_listings(tmp_path: Path):
    config = _make_test_env(tmp_path, [])
    res_backlog = _invoke_sw(config, ["backlog", "-k", "test", "--format", "rich"])
    assert res_backlog.exit_code == 0
    assert "No backlog items found." in res_backlog.output

    res_epics = _invoke_sw(config, ["epics", "-k", "test", "--format", "rich"])
    assert res_epics.exit_code == 0
    assert "No epics found." in res_epics.output

    res_comps = _invoke_sw(config, ["components", "-k", "test", "--format", "rich"])
    assert res_comps.exit_code == 0
    assert "No components found." in res_comps.output

    res_comp_json = _invoke_sw(config, ["components", "-k", "test", "--format", "json"])
    assert res_comp_json.exit_code == 0
    assert json.loads(res_comp_json.output) == []
