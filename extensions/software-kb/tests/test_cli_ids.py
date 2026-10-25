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

from typer.testing import CliRunner

import pyrite.cli
from pyrite.config import KBConfig
from tests._world import build_world

# Must import pyrite.cli before software-kb cli to ensure plugin loading order (#900)
cli = importlib.import_module("pyrite_software_kb.cli") if pyrite.cli else None


def _make_sw_world(tmp_path: Path):
    kb_path = tmp_path / "sw-kb"
    return build_world(
        tmp_path,
        kbs=[KBConfig(name="sw-kb", path=kb_path, kb_type="software")],
        rest=False,
    )


def _invoke_sw(world, args: list[str], columns: int = 80):
    runner = CliRunner()
    env = {"COLUMNS": str(columns), "TERM": "xterm-256color"}
    with world.pointed():
        return runner.invoke(cli.sw_app, args, env=env)


def test_sw_backlog_rich_preserves_30_char_id_at_80_columns(tmp_path: Path):
    item_id = "login-endpoint-auth-service-30"  # 30 chars
    assert len(item_id) == 30
    world = _make_sw_world(tmp_path)
    try:
        world.add_entry(
            "sw-kb",
            f"""---
id: {item_id}
type: backlog_item
title: Login endpoint implementation
status: accepted
priority: high
kind: feature
---

Login endpoint details.
""",
        )
        result = _invoke_sw(world, ["backlog", "-k", "sw-kb", "--format", "rich"], columns=80)
        assert result.exit_code == 0, result.output
        assert item_id in result.output
        lines_with_id = [line for line in result.output.splitlines() if item_id in line]
        assert len(lines_with_id) == 1
    finally:
        world.close()


def test_sw_backlog_grouped_rich_preserves_30_char_id_at_80_columns(tmp_path: Path):
    epic_id = "epic-for-user-authentication-30"
    item_id = "order-processing-queue-item-30"
    world = _make_sw_world(tmp_path)
    try:
        world.add_entry(
            "sw-kb",
            f"""---
id: {epic_id}
type: backlog_item
title: User Auth Epic
kind: epic
status: in_progress
priority: high
---

Auth Epic
""",
        )
        world.add_entry(
            "sw-kb",
            f"""---
id: {item_id}
type: backlog_item
title: Order processing queue
kind: feature
status: planned
priority: medium
links:
  - target: {epic_id}
    relation: subtask_of
---

Order queue
""",
        )
        result = _invoke_sw(
            world,
            ["backlog", "-k", "sw-kb", "--group-by", "epic", "--format", "rich"],
            columns=80,
        )
        assert result.exit_code == 0, result.output
        assert item_id in result.output
        lines_with_id = [line for line in result.output.splitlines() if item_id in line]
        assert len(lines_with_id) == 1
    finally:
        world.close()


def test_sw_epics_rich_preserves_30_char_id_at_80_columns(tmp_path: Path):
    epic_id = "epic-notification-pipeline-030"
    assert len(epic_id) == 30
    world = _make_sw_world(tmp_path)
    try:
        world.add_entry(
            "sw-kb",
            f"""---
id: {epic_id}
type: backlog_item
title: Notification Pipeline Epic
kind: epic
status: in_progress
priority: high
---

Pipeline Epic
""",
        )
        result = _invoke_sw(world, ["epics", "-k", "sw-kb", "--format", "rich"], columns=80)
        assert result.exit_code == 0, result.output
        assert epic_id in result.output
        lines_with_id = [line for line in result.output.splitlines() if epic_id in line]
        assert len(lines_with_id) == 1
    finally:
        world.close()


def test_sw_epic_detail_rich_preserves_30_char_id(tmp_path: Path):
    epic_id = "epic-database-migration-pipeline"
    item_id = "subtask-schema-migration-v2-30"
    assert len(item_id) == 30
    world = _make_sw_world(tmp_path)
    try:
        world.add_entry(
            "sw-kb",
            f"""---
id: {epic_id}
type: backlog_item
title: Database Migration
kind: epic
status: in_progress
priority: high
---

Migration Epic
""",
        )
        world.add_entry(
            "sw-kb",
            f"""---
id: {item_id}
type: backlog_item
title: Run schema migration script
kind: feature
status: in_progress
priority: high
links:
  - target: {epic_id}
    relation: subtask_of
---

Migration Script
""",
        )
        result = _invoke_sw(world, ["epic", epic_id, "-k", "sw-kb", "--format", "rich"], columns=80)
        assert result.exit_code == 0, result.output
        assert item_id in result.output
    finally:
        world.close()


def test_sw_adrs_rich_preserves_long_id_at_80_columns(tmp_path: Path):
    adr_id = "adr-distributed-event-bus-v2-30"
    assert len(adr_id) >= 30
    world = _make_sw_world(tmp_path)
    try:
        world.add_entry(
            "sw-kb",
            f"""---
id: {adr_id}
type: adr
title: Adopt Event Bus
status: accepted
adr_number: 1
---

ADR body
""",
        )
        result = _invoke_sw(world, ["adrs", "-k", "sw-kb", "--format", "rich"], columns=80)
        assert result.exit_code == 0, result.output
        assert adr_id in result.output
        lines_with_id = [line for line in result.output.splitlines() if adr_id in line]
        assert len(lines_with_id) == 1
    finally:
        world.close()


def test_sw_components_json_has_id_and_kb_name(tmp_path: Path):
    comp_id = "api-gateway-service-component-30"
    world = _make_sw_world(tmp_path)
    try:
        world.add_entry(
            "sw-kb",
            f"""---
id: {comp_id}
type: component
title: Api gateway
kind: service
path: services/gateway
owner: platform
---

Gateway component
""",
        )
        result = _invoke_sw(world, ["components", "-k", "sw-kb", "--format", "json"])
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == comp_id
        assert row["kb_name"] == "sw-kb"
        assert row["title"] == "Api gateway"
        assert row["kind"] == "service"
        assert row["path"] == "services/gateway"
        assert row["owner"] == "platform"
    finally:
        world.close()


def test_sw_components_rich_has_id_column_and_shows_id(tmp_path: Path):
    comp_id = "api-gateway-service-component-30"
    world = _make_sw_world(tmp_path)
    try:
        world.add_entry(
            "sw-kb",
            f"""---
id: {comp_id}
type: component
title: Api gateway
kind: service
path: services/gateway
owner: platform
---

Gateway component
""",
        )
        result = _invoke_sw(world, ["components", "-k", "sw-kb", "--format", "rich"], columns=80)
        assert result.exit_code == 0, result.output
        assert "ID" in result.output
        assert comp_id in result.output
        lines_with_id = [line for line in result.output.splitlines() if comp_id in line]
        assert len(lines_with_id) == 1
    finally:
        world.close()


def test_sw_empty_listings(tmp_path: Path):
    world = _make_sw_world(tmp_path)
    try:
        res_backlog = _invoke_sw(world, ["backlog", "-k", "sw-kb", "--format", "rich"])
        assert res_backlog.exit_code == 0
        assert "No backlog items found." in res_backlog.output

        res_epics = _invoke_sw(world, ["epics", "-k", "sw-kb", "--format", "rich"])
        assert res_epics.exit_code == 0
        assert "No epics found." in res_epics.output

        res_comps = _invoke_sw(world, ["components", "-k", "sw-kb", "--format", "rich"])
        assert res_comps.exit_code == 0
        assert "No components found." in res_comps.output

        res_comp_json = _invoke_sw(world, ["components", "-k", "sw-kb", "--format", "json"])
        assert res_comp_json.exit_code == 0
        assert json.loads(res_comp_json.output) == []
    finally:
        world.close()
