"""Tests that sw backlog, epics, and components preserve IDs and do not truncate (#1293)."""

from __future__ import annotations

import json

import pytest
import yaml
from pyrite_software_kb.cli import sw_app
from pyrite_software_kb.preset import SOFTWARE_KB_PRESET
from typer.testing import CliRunner

from pyrite.config import KBConfig, PyriteConfig, Settings, save_config
from pyrite.storage.database import PyriteDB
from pyrite.storage.index import IndexManager


@pytest.fixture
def sw_env(tmp_path, monkeypatch):
    kb_path = tmp_path / "sw-kb"
    kb_path.mkdir()
    (kb_path / "kb.yaml").write_text(yaml.safe_dump(SOFTWARE_KB_PRESET, sort_keys=False))
    db_path = tmp_path / "index.db"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = PyriteConfig(
        knowledge_bases=[KBConfig(name="sw-kb", path=kb_path, kb_type="software")],
        settings=Settings(index_path=db_path, auto_embed=False),
    )
    monkeypatch.setenv("PYRITE_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr("pyrite.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("pyrite.config.CONFIG_FILE", config_dir / "config.yaml")
    save_config(config)

    import pyrite_software_kb.cli as sw_cli

    monkeypatch.setattr(sw_cli.console, "_width", 80)
    monkeypatch.setattr(sw_cli.console, "_height", 25)

    db = PyriteDB(db_path)
    IndexManager(db, config).index_all()
    db.close()
    return {"config": config, "kb_path": kb_path, "db_path": db_path}


def test_sw_backlog_rich_format_preserves_full_id(sw_env):
    """A test runs sw backlog --format rich with COLUMNS=80 on an item whose id is 30 characters
    and finds the whole id in the output (#1293)."""
    long_id = "fix-order-total-rounding-error"
    assert len(long_id) == 30

    db = PyriteDB(sw_env["db_path"])
    db._raw_conn.execute(
        "INSERT OR REPLACE INTO kb (name, path, kb_type) VALUES (?, ?, ?)",
        ("sw-kb", str(sw_env["kb_path"]), "software"),
    )
    db._raw_conn.execute(
        "INSERT INTO entry (id, kb_name, entry_type, title, body, metadata, importance, status, priority, created_at, updated_at) "
        "VALUES (?, 'sw-kb', 'backlog_item', 'Fix order total rounding error', '', ?, 5, 'accepted', 'high', '2026-10-23T00:00:00', '2026-10-23T00:00:00')",
        (
            long_id,
            json.dumps({"kind": "bug", "status": "accepted", "priority": "high", "effort": "S"}),
        ),
    )
    db._raw_conn.commit()
    db.close()

    runner = CliRunner()
    result = runner.invoke(sw_app, ["backlog", "-k", "sw-kb", "--format", "rich"])

    assert result.exit_code == 0, result.output
    assert long_id in result.output, f"Expected full id '{long_id}' in output:\n{result.output}"


def test_sw_components_json_and_rich_include_id_and_kb_name(sw_env):
    """sw components JSON rows have id and kb_name, and rich table has ID and Title columns (#1293)."""
    comp_id = "api-gateway-service"
    comp_title = "API Gateway"
    db = PyriteDB(sw_env["db_path"])
    db._raw_conn.execute(
        "INSERT OR REPLACE INTO kb (name, path, kb_type) VALUES (?, ?, ?)",
        ("sw-kb", str(sw_env["kb_path"]), "software"),
    )
    db._raw_conn.execute(
        "INSERT INTO entry (id, kb_name, entry_type, title, body, metadata, importance, status, priority, created_at, updated_at) "
        "VALUES (?, 'sw-kb', 'component', ?, '', ?, 5, 'active', 'medium', '2026-10-23T00:00:00', '2026-10-23T00:00:00')",
        (
            comp_id,
            comp_title,
            json.dumps({"kind": "service", "path": "services/gateway", "owner": "infra"}),
        ),
    )
    db._raw_conn.commit()
    db.close()

    runner = CliRunner()
    # Test JSON output
    json_res = runner.invoke(sw_app, ["components", "-k", "sw-kb", "--format", "json"])
    assert json_res.exit_code == 0, json_res.output
    data = json.loads(json_res.output)
    assert len(data) == 1
    assert data[0]["id"] == comp_id
    assert data[0]["kb_name"] == "sw-kb"
    assert data[0]["title"] == comp_title
    assert data[0]["kind"] == "service"

    # Test Rich table output
    rich_res = runner.invoke(sw_app, ["components", "-k", "sw-kb", "--format", "rich"])
    assert rich_res.exit_code == 0, rich_res.output
    assert comp_id in rich_res.output
    assert comp_title in rich_res.output, f"Expected title '{comp_title}' in Rich output:\n{rich_res.output}"


def test_sw_epics_and_epic_detail_preserve_full_id(sw_env):
    """sw epics table and sw epic detail preserve long IDs without truncation (#1293)."""
    long_epic_id = "epic-customer-billing-portal-v2"
    long_item_id = "item-recurring-subscription-billing"

    db = PyriteDB(sw_env["db_path"])
    db._raw_conn.execute(
        "INSERT OR REPLACE INTO kb (name, path, kb_type) VALUES (?, ?, ?)",
        ("sw-kb", str(sw_env["kb_path"]), "software"),
    )
    db._raw_conn.execute(
        "INSERT INTO entry (id, kb_name, entry_type, title, body, metadata, importance, status, priority, created_at, updated_at) "
        "VALUES (?, 'sw-kb', 'backlog_item', 'Customer Billing Portal V2', '', ?, 5, 'active', 'high', '2026-10-23T00:00:00', '2026-10-23T00:00:00')",
        (long_epic_id, json.dumps({"kind": "epic", "status": "active", "priority": "high"})),
    )
    db._raw_conn.execute(
        "INSERT INTO entry (id, kb_name, entry_type, title, body, metadata, importance, status, priority, created_at, updated_at) "
        "VALUES (?, 'sw-kb', 'backlog_item', 'Recurring subscription billing', '', ?, 5, 'in_progress', 'high', '2026-10-23T00:00:00', '2026-10-23T00:00:00')",
        (long_item_id, json.dumps({"epic": long_epic_id, "status": "in_progress", "priority": "high"})),
    )
    db._raw_conn.execute(
        "INSERT INTO link (source_id, source_kb, target_id, target_kb, relation, inverse_relation) "
        "VALUES (?, 'sw-kb', ?, 'sw-kb', 'has_subtask', 'subtask_of')",
        (long_epic_id, long_item_id),
    )
    db._raw_conn.commit()
    db.close()

    runner = CliRunner()
    # 1. sw epics table
    epics_res = runner.invoke(sw_app, ["epics", "-k", "sw-kb", "--format", "rich"])
    assert epics_res.exit_code == 0, epics_res.output
    assert long_epic_id in epics_res.output

    # 2. sw epic detail
    epic_res = runner.invoke(sw_app, ["epic", long_epic_id, "-k", "sw-kb", "--format", "rich"])
    assert epic_res.exit_code == 0, epic_res.output
    assert long_item_id in epic_res.output
