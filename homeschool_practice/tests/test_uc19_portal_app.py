# -*- coding: utf-8 -*-
"""UC-19 — Practice inside the homeschool portal app (Bemade portal kit).

Acceptance criteria
-------------------
1. With the kit's switch on, the learner's « Today » shows the day's quests (label and
   progress only), each open one with « Start » opening it in the game
   (``/my/homeschool/practice?quest=<id>``); the nav has « Practice » (the game).
2. The game stays full screen (its own page, no app shell) and its home screen has a ✕
   back to « Today » (``/my/home``; the stock homeschool page when the app is off).
   It opens a quest named in the URL once.
3. One installed app: the practice page links no manifest of its own and
   ``/my/homeschool/practice/manifest.webmanifest`` is gone; the app's manifest
   (``/my/app/homeschool.webmanifest``, ``/my/app.webmanifest`` where homeschool is
   the default app) has « Today » then « Practice » as shortcuts.
4. A tutor's « Practice » is a read-only page per learner: the units unlocked by deck,
   the proficiency of each and when it was last practised. The learner's own login gets
   a 403 there; an unrelated student is a 404.
5. No mastery state, box, threshold or timing appears on a learner-facing page or
   payload (« Today », the game page, the home payload).
6. A login that is both a learner and a tutor gets both « Practice » entries: the game
   for himself, the progress page for the learner he follows.
7. Practice's entries (nav, page, widget, shortcut) are the homeschool app's
   (``homeschool``, kit 19.0.1.15.0); an upgrade over an older kit stops first.
"""
import json

from odoo import Command
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.homeschool_portal.tests.test_portal_app_apps import assert_kit_guard
from odoo.addons.homeschool_practice.controllers.api import FORBIDDEN_KEYS

from .common import PracticeHttpCase

SHELL = 'data-pk-app-shell="1"'
SWITCH = "bemade_portal_kit.enabled"


@tagged("post_install", "-at_install")
class TestPracticePortalApp(PracticeHttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(SWITCH, "1")
        cls.t7 = cls.deck.unit_ids.filtered(lambda u: u.sequence == 7)

    def get(self, url, **kw):
        return self.url_open(url, **kw)

    def practise_t7(self):
        """A finished session on the 7 table, every answer right."""
        session = self.env["homeschool.practice.session"]._start(self.student, self.deck, kind="unit", unit=self.t7)
        while session._current_item():
            item = session._current_item()
            session._answer(item, item.answer, first_touch_ms=900, submit_ms=1300)
        session._finish()

    # 1 -------------------------------------------------------------------
    def test_today_has_the_quests(self):
        self.authenticate("hs_learner", "hs_learner")
        body = self.get("/my/home").text
        self.assertIn(SHELL, body)
        self.assertIn('data-pk-dash-widget="hs_quests"', body)
        quests = self.env["homeschool.practice.quest"].search([("student_id", "=", self.student.id)])
        self.assertTrue(quests)
        for quest in quests:
            self.assertIn('data-hs-quest="%d"' % quest.id, body)
            self.assertIn('href="/my/homeschool/practice?quest=%d"' % quest.id, body)
        self.assertIn('data-pk-nav-key="hs_practice"', body)
        self.assertNotIn('data-pk-nav-key="hs_practice_progress"', body)
        self.assertIn('href="/my/homeschool/practice"', body)

    def test_quests_once_a_day(self):
        self.authenticate("hs_learner", "hs_learner")
        self.get("/my/home")
        drawn = self.env["homeschool.practice.quest"].search([("student_id", "=", self.student.id)])
        self.get("/my/home")
        self.call("/home")
        self.assertEqual(self.env["homeschool.practice.quest"].search([("student_id", "=", self.student.id)]), drawn)

    # 2 -------------------------------------------------------------------
    def test_game_full_screen_with_a_way_back(self):
        self.authenticate("hs_learner", "hs_learner")
        html = self.get("/my/homeschool/practice").text
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertNotIn(SHELL, html)
        self.assertIn('data-exit-url="/my/home"', html)
        js = self.get("/homeschool_practice/static/src/js/practice.js").text
        home = js[js.index("function renderHome("):js.index("function fmt(")]
        self.assertIn('id="hp-exit" href="\' + esc(EXIT_URL)', home)
        self.assertIn('data-exit-url', js)
        load = js[js.index("function loadHome("):js.index("function renderHome(")]
        self.assertIn("start({ quest_id: quest.id })", load)
        self.assertIn('get("quest")', js)
        self.assertEqual(self.call("/home")["labels"]["exit"], "Retour à aujourd’hui")
        # the app off: back to the stock homeschool page
        self.env["ir.config_parameter"].sudo().set_param(SWITCH, "0")
        self.assertIn('data-exit-url="/my/homeschool"', self.get("/my/homeschool/practice").text)

    # 3 -------------------------------------------------------------------
    def test_one_installed_app(self):
        self.authenticate("hs_learner", "hs_learner")
        html = self.get("/my/homeschool/practice").text
        self.assertNotIn('rel="manifest"', html)
        self.assertNotIn("apple-touch-icon", html)
        self.assertEqual(self.get("/my/homeschool/practice/manifest.webmanifest").status_code, 404)
        # The homeschool app's manifest (also /my/app.webmanifest where it is the
        # database's default app, e.g. the homeschool instance).
        self.env["ir.config_parameter"].sudo().set_param("bemade_portal_kit.default_app", "homeschool")
        for url in ("/my/app/homeschool.webmanifest", "/my/app.webmanifest"):
            manifest = json.loads(self.get(url).text)
            self.assertEqual(manifest["start_url"], "/my/home", url)
            urls = [s["url"] for s in manifest.get("shortcuts", [])]
            self.assertEqual(urls, ["/my/home", "/my/homeschool/practice"], url)

    # 4 -------------------------------------------------------------------
    def test_tutor_progress_page(self):
        self.practise_t7()
        self.authenticate("hs_teacher", "hs_teacher")
        body = self.get("/my/home").text
        self.assertIn('data-pk-nav-key="hs_practice_progress"', body)
        self.assertNotIn('data-pk-nav-key="hs_practice"', body)
        self.assertIn('data-pk-dash-widget="hs_quests"', body)
        self.assertNotIn("/my/homeschool/practice?quest=", body)  # a tutor reads the quests
        res = self.get("/my/homeschool/practice/progress", allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        url = "/my/homeschool/%d/practice/progress" % self.student.id
        self.assertTrue(res.headers["Location"].endswith(url))
        res = self.get(url)
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn(SHELL, body)
        self.assertIn('data-hs-deck="%d"' % self.deck.id, body)
        self.assertIn('data-hs-unit="%d"' % self.t7.id, body)
        self.assertIn("%s %%" % self.t7._proficiency(self.student), body)
        # how often: one session on the 7 table, one answer per item asked
        answers = self.env["homeschool.practice.attempt"].search_count(
            [("session_id.student_id", "=", self.student.id), ("item_id.unit_id", "=", self.t7.id)])
        self.assertRegex(body, r'(?s)data-hs-unit="%d">.*?data-hs-sessions="1">1</td>.*?data-hs-answers="1">%d</td>'
                         % (self.t7.id, answers), "sessions and answers per unit")
        t3 = self.deck.unit_ids.filtered(lambda u: u.sequence == 3)
        self.assertNotIn('data-hs-unit="%d"' % t3.id, body)  # still locked

    @mute_logger("odoo.http")
    def test_progress_never_for_the_learner(self):
        self.authenticate("hs_learner", "hs_learner")
        self.assertEqual(self.get("/my/homeschool/%d/practice/progress" % self.student.id).status_code, 403)
        self.assertEqual(self.get("/my/homeschool/practice/progress").status_code, 403)
        self.assertEqual(self.get("/my/homeschool/%d/practice/progress" % self.other_student.id).status_code, 404)
        self.authenticate("hs_teacher", "hs_teacher")
        self.assertEqual(self.get("/my/homeschool/%d/practice/progress" % self.other_student.id).status_code, 404)

    # 5 -------------------------------------------------------------------
    def test_no_mastery_on_learner_pages(self):
        self.practise_t7()
        self.authenticate("hs_learner", "hs_learner")
        for url in ("/my/home", "/my/homeschool/practice"):
            body = self.get(url).text
            for word in ("hs_practice_progress", "data-hs-unit", "Proficiency", "Maîtrise", "first_touch", "submit_ms",
                         "threshold", "automatic"):
                self.assertNotIn(word, body, (url, word))
        home = self.call("/home")
        for key in FORBIDDEN_KEYS:
            self.assertNotIn('"%s"' % key, json.dumps(home), key)

    # 6 -------------------------------------------------------------------
    def test_learner_who_is_also_a_tutor(self):
        self.other_student.resource_user_ids = [Command.link(self.learner.id)]
        self.authenticate("hs_learner", "hs_learner")
        body = self.get("/my/home").text
        self.assertIn('data-pk-nav-key="hs_practice"', body)
        self.assertIn('data-pk-nav-key="hs_practice_progress"', body)
        self.assertEqual(self.get("/my/homeschool/%d/practice/progress" % self.other_student.id).status_code, 200)
        with mute_logger("odoo.http"):
            self.assertEqual(self.get("/my/homeschool/%d/practice/progress" % self.student.id).status_code, 403)

    # 7 -------------------------------------------------------------------
    def test_entries_are_the_homeschool_apps(self):
        kit = self.env["portal.kit"]
        entries = {e["key"]: e for e in kit.pk_nav_entries(app="homeschool")}
        self.assertEqual((entries["hs_practice"]["app"], entries["hs_practice_progress"]["app"]),
                         ("homeschool", "homeschool"))
        self.assertEqual(kit.pk_pages(app="homeschool")["hs_practice_progress"].app, "homeschool")
        widgets = {w["key"]: w for w in self.env["portal.kit.dashboard"]._pk_widgets()}
        self.assertEqual(widgets["hs_quests"]["app"], "homeschool")

    @mute_logger("odoo.addons.bemade_portal_kit.tools.version_guard")
    def test_kit_version_guard(self):
        assert_kit_guard(self, "homeschool_practice")
