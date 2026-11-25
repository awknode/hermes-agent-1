"""`hermes kanban dispatch` says WHY a card is not spawnable here, instead of calling every case OK.

Three different conditions share the ``skipped_nonspawnable`` bucket: a lane a plugin runs on
another host (expected), an assignee with no profile on this host (a typo, or an external
worker's lane), and an existing profile this home's ``kanban.dispatch_profiles`` leaves out
(the card never runs and nothing said so).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_db_connect as kbc
from hermes_cli import kanban_ops
from hermes_cli import profiles_run_elsewhere


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _dispatch(capsys, *, as_json: bool):
    args = argparse.Namespace(dry_run=True, max=None, failure_limit=2, json=as_json)
    assert kanban_ops._cmd_dispatch(args) == 0
    out = capsys.readouterr().out
    return json.loads(out) if as_json else out


def _card(assignee: str) -> str:
    with kbc.connect() as conn:
        return kb.create_task(conn, title="card", assignee=assignee)


def test_missing_profile_is_named_not_called_ok(kanban_home, capsys):
    tid = _card("ghost")
    out = _dispatch(capsys, as_json=False)
    assert f"{tid}: no profile 'ghost' here" in out
    assert "OK" not in out
    assert _dispatch(capsys, as_json=True)["skipped_nonspawnable_reasons"] == {tid: "no_profile"}


def test_profile_left_out_of_dispatch_profiles_says_so(kanban_home, capsys, all_assignees_spawnable, monkeypatch):
    monkeypatch.setattr(profiles_run_elsewhere, "home_runs_elsewhere", lambda _dir: False)
    (kanban_home / "config.yaml").write_text("kanban:\n  dispatch_profiles: [sage]\n", encoding="utf-8")
    tid = _card("coder")
    out = _dispatch(capsys, as_json=False)
    assert "'coder' is not in kanban.dispatch_profiles" in out
    assert _dispatch(capsys, as_json=True)["skipped_nonspawnable_reasons"] == {tid: "not_in_dispatch_profiles"}


def test_lane_run_elsewhere_is_the_ok_case(kanban_home, capsys, all_assignees_spawnable, monkeypatch):
    monkeypatch.setattr(profiles_run_elsewhere, "home_runs_elsewhere", lambda _dir: True)
    tid = _card("remote")
    out = _dispatch(capsys, as_json=False)
    assert f"{tid}: 'remote' runs on another host through a plugin lane (OK)" in out
    assert _dispatch(capsys, as_json=True)["skipped_nonspawnable_reasons"] == {tid: "runs_elsewhere"}
