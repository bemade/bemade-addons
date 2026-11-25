# -*- coding: utf-8 -*-
"""UC-P7 — The homeschool portal is one app of the kit (``homeschool``, kit 19.0.1.15.0).

Another kit app may be installed in the same database (the shared addons CI installs
every consumer). The kit tests cover the mechanism; this checks the homeschool
registrations use it. A synthetic second app (« north », registered FIRST: the
database's default app, lowest sequence) stands for the other consumer.

Acceptance criteria
-------------------
1. The homeschool registry is the app ``homeschool``: its roles, nav entries, pages
   (``/my/home`` = Today, « Configure » under Today) and its registration (layout,
   home, installable app). Its roles no longer include an ``internal`` role of its own.
2. A learner is in the homeschool app even though « north » is the default app:
   ``/my/home`` is Today with the homeschool nav only; the kit's own page (« More »)
   is drawn on the homeschool layout with the homeschool nav; the shell links the
   homeschool app's manifest.
3. A user of the other app never sees the homeschool app: no homeschool nav entry,
   widget or page on its ``/my/home`` or « More ».
4. Version guard: an upgrade of ``homeschool_portal`` / ``homeschool_practice`` over a
   kit older than ``PK_MIN_VERSION`` stops before anything is written.
Synthetic users and app only.
"""
import importlib.util
import os
from contextlib import contextmanager
from unittest.mock import patch

from odoo import fields
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tests.common import pk_hooks
from odoo.addons.bemade_portal_kit.tools import pk_nav, pk_static_page
from odoo.addons.bemade_portal_kit.tools.version_guard import PkKitVersionError

from .common import HomeschoolPortalCase

SHELL = 'data-pk-app-shell="1"'
SWITCH = "bemade_portal_kit.enabled"
NORTH_LOGIN = "hsp_north"


@contextmanager
def north_app(env):
    """A second kit app, « north », first in order (the default app), with one user."""
    users = type(env["res.users"])
    original_roles = users._pk_extra_roles

    def extra_roles(user):
        roles = original_roles(user)
        return roles | {"n_member"} if user.login == NORTH_LOGIN else roles

    def apps(orig):
        out = dict(orig)
        out["north"] = {"sequence": 1}
        return out

    with patch.object(users, "_pk_extra_roles", extra_roles), pk_hooks(
        env,
        _pk_roles=lambda orig: dict(orig, n_member={"groups": (), "app": "north"}),
        _pk_apps=apps,
        _pk_nav=lambda orig: list(orig) + [
            pk_nav("n_tab", "North Tab", "home", "/my/north-tab", {"n_member"}, 10, ("tab", "rail"), app="north"),
            pk_nav("n_more", "North More", "more", "/my/app/more", {"n_member"}, 90, ("rail",), app="north"),
        ],
        _pk_pages=lambda orig: list(orig) + [
            pk_static_page("n_tab_page", "/my/north-tab", "North Tab", app="north"),
        ],
    ):
        yield


def assert_kit_guard(case, module):
    """``module``'s ``0.0.0`` pre-migration stops on a kit older than ``PK_MIN_VERSION``
    and is a no-op on the installed one."""
    path = os.path.join(get_module_path(module), "migrations", "0.0.0", "pre-kit-version-guard.py")
    spec = importlib.util.spec_from_file_location("hs_pre_kit_guard_%s" % module, path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    case.assertIsNone(script.migrate(case.env.cr, "19.0.0.0.0"))
    case.env.cr.execute(
        "UPDATE ir_module_module SET latest_version = '19.0.1.14.0' WHERE name = 'bemade_portal_kit'")
    with case.assertRaises(PkKitVersionError) as ctx:
        script.migrate(case.env.cr, "19.0.0.0.0")
    case.assertIn("%s needs bemade_portal_kit >=" % module, str(ctx.exception))


@tagged("post_install", "-at_install")
class TestPortalAppRegistry(TransactionCase):

    # 1 -------------------------------------------------------------------
    def test_homeschool_is_one_app(self):
        kit = self.env["portal.kit"]
        roles = kit.pk_roles()
        self.assertEqual((roles["learner"]["app"], roles["tutor"]["app"]), ("homeschool", "homeschool"))
        self.assertIn("homeschool", kit.pk_apps())
        spec = kit.pk_app_spec("homeschool")
        self.assertEqual(spec["layout"], "homeschool_portal.hs_app_layout")
        self.assertEqual(spec["home"], "homeschool_portal.hs_dash_page")
        self.assertEqual(spec["home_render"], "_hs_dash_render")
        self.assertEqual((spec["pwa"]["start_url"], spec["pwa"]["manifest_id"]), ("/my/home", "/my/home"))
        self.assertNotIn("brand", spec)  # the company's name (the kit's default)
        hs_nav = [e for e in kit.pk_nav_entries(app="homeschool") if e["key"].startswith("hs_")]
        self.assertTrue(hs_nav)
        self.assertTrue(all(e["app"] == "homeschool" for e in hs_nav))
        pages = kit.pk_pages(app="homeschool")
        self.assertTrue(all(p.app == "homeschool" for k, p in pages.items() if k.startswith("hs_")))
        self.assertEqual(kit.pk_match_url("/my/home", app="homeschool")[0], "hs_dash_page")
        self.assertNotIn("pk_dash_page", pages)
        self.assertEqual(pages["pk_dash_configure"].app, "homeschool")
        crumbs = kit.pk_resolve("pk_dash_configure", {}, app="homeschool")["crumbs"]
        self.assertEqual([url for _label, url in crumbs], ["/my/home"])

    def test_widgets_are_the_apps(self):
        widgets = self.env["portal.kit.dashboard"]._pk_widgets()
        hs = [w for w in widgets if w["key"].startswith("hs_")]
        self.assertTrue(hs)
        self.assertTrue(all(w["app"] == "homeschool" for w in hs))

    def test_never_in_another_app(self):
        kit = self.env["portal.kit"]
        with north_app(self.env):
            self.assertEqual(kit._pk_default_app(), "north")
            self.assertFalse([e for e in kit.pk_nav_entries(app="north") if e["key"].startswith("hs_")])
            self.assertFalse([k for k in kit.pk_pages(app="north") if k.startswith("hs_")])
            self.assertNotEqual((kit.pk_match_url("/my/home", app="north") or ("",))[0], "hs_dash_page")
            self.assertFalse(kit._pk_pwa_shortcuts("north"))

    # 4 -------------------------------------------------------------------
    @mute_logger("odoo.addons.bemade_portal_kit.tools.version_guard")
    def test_version_guard(self):
        assert_kit_guard(self, "homeschool_portal")


@tagged("post_install", "-at_install")
class TestPortalAppNotMixed(HomeschoolPortalCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env["ir.config_parameter"].sudo().set_param(SWITCH, "1")
        day = env["homeschool.day"].create({
            "student_id": cls.student.id, "date": fields.Date.context_today(cls.student_user)})
        env["homeschool.deliverable"].create({"day_id": day.id, "name": "Glue the fraction strip"})
        cls.north_user = cls.env["res.users"].create({
            "name": "North Member", "login": NORTH_LOGIN, "password": NORTH_LOGIN,
            "group_ids": [(6, 0, [env.ref("base.group_portal").id])],
        })

    # 2 -------------------------------------------------------------------
    def test_learner_stays_in_homeschool(self):
        with north_app(self.env):
            self.assertEqual(self.env["portal.kit"].with_user(self.student_user)._pk_app(), "homeschool")
            self.login(self.student_user)
            body = self.text(self.get("/my/home"))
            self.assertIn(SHELL, body)
            self.assertIn('data-pk-dash-widget="hs_list"', body)
            self.assertIn("Glue the fraction strip", body)
            self.assertIn("/my/homeschool/week", body)
            self.assertNotIn("/my/north-tab", body)
            self.assertIn("/my/app/homeschool.webmanifest", body)
            more = self.text(self.get("/my/app/more"))
            self.assertIn(SHELL, more)
            self.assertIn("o_hs_content", more)  # the homeschool layout
            self.assertIn("/my/homeschool/week", more)
            self.assertNotIn("/my/north-tab", more)

    # 3 -------------------------------------------------------------------
    def test_other_app_user_never_sees_homeschool(self):
        with north_app(self.env):
            self.assertEqual(self.env["portal.kit"].with_user(self.north_user)._pk_app(), "north")
            self.login(self.north_user)
            for url in ("/my/home", "/my/app/more"):
                body = self.text(self.get(url))
                self.assertIn(SHELL, body, url)
                self.assertIn("/my/north-tab", body, url)
                self.assertNotIn("/my/homeschool", body, url)
                self.assertNotIn("data-pk-dash-widget=\"hs_", body, url)
                self.assertNotIn("o_hs_content", body, url)
