"""Tests that sw backlog rich table does not truncate IDs and sw components outputs ID (#1293)."""

import json
from unittest.mock import patch

import pytest
import yaml
from pyrite_software_kb.cli import sw_app
from pyrite_software_kb.preset import SOFTWARE_KB_PRESET
from typer.testing import CliRunner

from pyrite.config import KBConfig, PyriteConfig, Settings
from pyrite.storage.database import PyriteDB
from pyrite.storage.index import IndexManager


@pytest.fixture
def sw_env(tmp_path):
    kb_path = tmp_path / "sw-kb"
    kb_path.mkdir()
    (kb_path / "kb.yaml").write_text(yaml.safe_dump(SOFTWARE_KB_PRESET, sort_keys=False))
    db_path = tmp_path / "index.db"
    config = PyriteConfig(
        knowledge_bases=[KBConfig(name="sw-kb", path=kb_path, kb_type="software")],
        settings=Settings(index_path=db_path, auto_embed=False),
    )
    db = PyriteDB(db_path)
    IndexManager(db, config).index_all()
    db.close()
    return {"config": config, "kb_path": kb_path, "db_path": db_path}


def test_sw_backlog_rich_format_preserves_full_id_with_columns_80(sw_env):
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
    with (
        patch("pyrite.config.load_config", return_value=sw_env["config"]),
        patch("pyrite_software_kb.cli.load_config", return_value=sw_env["config"]),
    ):
        result = runner.invoke(
            sw_app, ["backlog", "-k", "sw-kb", "--format", "rich"], env={"COLUMNS": "80"}
        )

    assert result.exit_code == 0, result.output
    assert long_id in result.output, f"Expected full id '{long_id}' in output:\n{result.output}"


def test_sw_components_json_and_rich_include_id_and_kb_name(sw_env):
    """sw components JSON rows have id and kb_name, and rich table has ID column (#1293)."""
    comp_id = "api-gateway-service"
    db = PyriteDB(sw_env["db_path"])
    db._raw_conn.execute(
        "INSERT OR REPLACE INTO kb (name, path, kb_type) VALUES (?, ?, ?)",
        ("sw-kb", str(sw_env["kb_path"]), "software"),
    )
    db._raw_conn.execute(
        "INSERT INTO entry (id, kb_name, entry_type, title, body, metadata, importance, status, priority, created_at, updated_at) "
        "VALUES (?, 'sw-kb', 'component', 'API Gateway', '', ?, 5, 'active', 'medium', '2026-10-23T00:00:00', '2026-10-23T00:00:00')",
        (comp_id, json.dumps({"kind": "service", "path": "services/gateway", "owner": "infra"})),
    )
    db._raw_conn.commit()
    db.close()

    runner = CliRunner()
    # Test JSON output
    with (
        patch("pyrite.config.load_config", return_value=sw_env["config"]),
        patch("pyrite_software_kb.cli.load_config", return_value=sw_env["config"]),
    ):
        json_res = runner.invoke(sw_app, ["components", "-k", "sw-kb", "--format", "json"])

    assert json_res.exit_code == 0, json_res.output
    data = json.loads(json_res.output)
    assert len(data) == 1
    assert data[0]["id"] == comp_id
    assert data[0]["kb_name"] == "sw-kb"
    assert data[0]["title"] == "API Gateway"
    assert data[0]["kind"] == "service"

    # Test Rich table output
    with (
        patch("pyrite.config.load_config", return_value=sw_env["config"]),
        patch("pyrite_software_kb.cli.load_config", return_value=sw_env["config"]),
    ):
        rich_res = runner.invoke(sw_app, ["components", "-k", "sw-kb", "--format", "rich"])

    assert rich_res.exit_code == 0, rich_res.output
    assert comp_id in rich_res.output
