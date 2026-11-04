# -*- coding: utf-8 -*-
"""UC-P5 — French for a fr_CA user.

Acceptance criteria
-------------------
1. With ``fr_CA`` active and the terms of the core and of this module loaded, a user
   whose language is ``fr_CA`` gets the pages in French: the home, the day (nav, list,
   material, the block kinds from the core's selection), the week (day headers from
   ``day.display_name``), the traces (submission button, the subjects' names) and the
   reading log. On the homeschool project there is no
   ``website``: the user's own language drives the rendering. On a database where
   ``website`` IS installed (the shared addons CI), the portal language follows the
   website instead, so the test also activates fr_CA on the website and sets the
   ``frontend_lang`` cookie — a no-op otherwise.
2. A user left in English keeps English.
"""
from odoo import Command
from odoo.tests import tagged

from .common import HomeschoolPortalCase


@tagged("post_install", "-at_install")
class TestPortalI18n(HomeschoolPortalCase):

    def _website_installed(self):
        return self.env["ir.module.module"]._get("website").state == "installed"

    def _frontend_lang(self, code):
        """With ``website`` installed the portal language follows the website, not the
        user: make the language available on every website and select it through the
        ``frontend_lang`` cookie. No-op without ``website``."""
        if not self._website_installed():
            return
        lang = self.env["res.lang"]._lang_get(code)
        for website in self.env["website"].sudo().search([]):
            if lang not in website.language_ids:
                website.language_ids = [Command.link(lang.id)]
        self.opener.cookies.set("frontend_lang", code)

    def test_fr_ca_user_gets_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(["homeschool", "homeschool_portal"], ["fr_CA"])
        self.student_user.lang = "fr_CA"
        self.login(self.student_user)
        self._frontend_lang("fr_CA")
        res = self.get("/my/homeschool")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("Mon école", body)
        self.assertIn("Aujourd'hui", body)
        self.assertIn("Carnet de lecture", body)
        self.assertNotIn("My school", body)
        body = self.text(self.get(self.base() + "/day/2026-03-02"))
        self.assertIn("Liste du jour", body)
        self.assertIn("Matériel du jour", body)
        self.assertIn("Critères de réussite", body)
        self.assertIn("Ouverture", body)   # block kind, from the core's selection
        self.assertIn("Lecture", body)
        self.assertIn("Français", body)    # the block's subject, translated by the core
        self.assertNotIn("Success criteria", body)
        body = self.text(self.get(self.base() + "/week/2026-W10"))
        self.assertIn("lun. 2 mars", body)  # day.display_name in the user's language
        self.assertIn("mer. 4 mars", body)
        self.assertNotIn("Mon 2 Mar", body)
        body = self.text(self.get(self.base() + "/traces"))
        self.assertIn("Déposer une trace", body)
        self.assertIn("En attente de validation", body)
        self.assertIn("Mathématiques", body)
        body = self.text(self.get("%s/traces/%d" % (self.base(), self.trace_inst.id)))
        self.assertIn("Matières", body)
        self.assertIn("Français", body)
        body = self.text(self.get(self.base() + "/traces/submit"))
        self.assertIn("Dans tes mots", body)
        body = self.text(self.get(self.base() + "/reading/%d" % self.book.id))
        self.assertIn("La page du vendredi", body)
        body = self.text(self.get("/my"))
        self.assertIn("Mon école", body)
        # the teacher, still in English
        self.login(self.teacher)
        self._frontend_lang("en_US")
        body = self.text(self.get("/my/homeschool"))
        self.assertIn("My students", body)
        self.assertNotIn("Mes élèves", body)
        self.assertIn("Mon 2 Mar", self.text(self.get(self.base() + "/week/2026-W10")))
