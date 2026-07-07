"""Tests for the fan-out planning logic (the git/forge orchestration is
integration-only and exercised in CI)."""
from pathlib import Path

import vendor_fanout as fo


def test_bump_branch_naming():
    assert fo.bump_branch("bemade_fsm", "19.0.1.3.2") == "vendor-bump/bemade_fsm-19.0.1.3.2"


def test_load_consumers(tmp_path):
    reg = tmp_path / "consumers.yml"
    reg.write_text(
        "consumers:\n"
        "  - url: https://git.bemade.org/durpro/odoo.git\n"
        "    branch: '19.0'\n"
        "  - url: https://git.bemade.org/rwi/odoo.git\n"
    )
    got = fo.load_consumers(str(reg))
    assert got[0]["url"].endswith("durpro/odoo.git")
    assert got[0]["branch"] == "19.0"
    assert "branch" not in got[1]


def test_load_consumers_empty_registry(tmp_path):
    reg = tmp_path / "consumers.yml"
    reg.write_text("consumers: []\n")
    assert fo.load_consumers(str(reg)) == []
    assert fo.load_consumers(str(tmp_path / "nope.yml")) == []


def test_lockfile_addons(tmp_path):
    (tmp_path / "addons.lock").write_text(
        "bemade_fsm:\n  source: github.com/bemade/bemade-addons\n  commit: abc\n"
        "other_addon:\n  source: x\n  commit: def\n"
    )
    assert fo.lockfile_addons(str(tmp_path)) == {"bemade_fsm", "other_addon"}


def test_lockfile_addons_missing(tmp_path):
    assert fo.lockfile_addons(str(tmp_path)) == set()


def test_plan_fanout_only_pinning_consumers():
    created = [
        {"addon": "bemade_fsm", "version": "19.0.1.3.2", "tag": "bemade_fsm/19.0.1.3.2"},
        {"addon": "unused_addon", "version": "19.0.1.0.0", "tag": "unused_addon/19.0.1.0.0"},
    ]
    consumer_pins = {
        "https://git.bemade.org/durpro/odoo.git": {"bemade_fsm", "bemade_helpdesk"},
        "https://git.bemade.org/rwi/odoo.git": {"bemade_margin_vendor_pricelist"},
    }
    items = fo.plan_fanout(created, consumer_pins)
    # Only durpro pins bemade_fsm; unused_addon is pinned by nobody.
    assert items == [
        {
            "url": "https://git.bemade.org/durpro/odoo.git",
            "addon": "bemade_fsm",
            "version": "19.0.1.3.2",
            "branch": "vendor-bump/bemade_fsm-19.0.1.3.2",
        }
    ]


def test_plan_fanout_multiple_consumers_same_addon():
    created = [{"addon": "bemade_fsm", "version": "19.0.2.0.0", "tag": "bemade_fsm/19.0.2.0.0"}]
    consumer_pins = {
        "https://git.bemade.org/a/odoo.git": {"bemade_fsm"},
        "https://git.bemade.org/b/odoo.git": {"bemade_fsm"},
        "https://git.bemade.org/c/odoo.git": {"something_else"},
    }
    items = fo.plan_fanout(created, consumer_pins)
    assert {i["url"] for i in items} == {
        "https://git.bemade.org/a/odoo.git",
        "https://git.bemade.org/b/odoo.git",
    }


def test_auth_url_injects_token(monkeypatch):
    monkeypatch.setenv("CI_BOT_TOKEN", "sekret")
    assert (
        fo._auth_url("https://git.bemade.org/durpro/odoo.git")
        == "https://oauth2:sekret@git.bemade.org/durpro/odoo.git"
    )
    # GitHub URLs are left untouched (gh handles their auth).
    assert fo._auth_url("https://github.com/bemade/x.git") == "https://github.com/bemade/x.git"
