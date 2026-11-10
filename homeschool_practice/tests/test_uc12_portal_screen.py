# -*- coding: utf-8 -*-
"""UC-12 — Portal practice screen (touch first, progress always in sight).

Acceptance criteria
-------------------
1. ``homeschool.student``: ``practice_handedness`` (``right`` | ``left``, default
   ``right``) and ``practice_weekdays`` (UC-07 §7), set by a manager; the lesson screen
   puts the keypad / choices on the dominant-hand side.
2. ``/my/homeschool/practice`` (the home) shows, without scrolling on an iPad in
   landscape: the day's quests as cards to pick from, the level and XP bar, the day /
   week / month goals, the reward balances (« en banque », per type) and the latest
   badges. A link appears on the homeschool portal home card.
3. The lesson screen has **no text input** (no iPad keyboard): keypad items use an
   on-screen number pad (0–9, erase, « Valider »); choices items use large buttons. No
   clock, countdown or speed anywhere; no item-level « je le sais » label.
4. Celebration on every finished session, quest, goal, level and badge (praise for the
   work done, not for speed or for « knowing »).
5. Touch targets ≥ 64 px; zoom gestures disabled on the page; a web-app manifest so it
   can be added to the iPad home screen and open full screen. Target: Safari on
   iPadOS 17 and later.
6. Answers not yet sent (no network) are queued on the device and sent in order when
   the connection returns (each with its ``client_uuid``).
7. Rendering is checked by HttpCase tests; real touch behaviour is checked by hand on
   the iPad before release (noted in the review artifact).
"""
import json

from odoo.tests import tagged

from .common import PracticeHttpCase

@tagged("post_install", "-at_install")
class TestPortalScreen(PracticeHttpCase):

    def test_page_renders_touch_first(self):
        self.authenticate("hs_learner", "hs_learner")
        r = self.url_open("/my/homeschool/practice")
        self.assertEqual(r.status_code, 200)
        html = r.text
        self.assertIn('user-scalable=no', html)
        self.assertIn('rel="manifest"', html)
        self.assertIn('data-handedness="right"', html)
        self.assertNotIn("<input", html)
        js = self.url_open("/homeschool_practice/static/src/js/practice.js").text
        self.assertNotIn("<input", js)
        self.assertNotIn("setInterval", js)  # no clock anywhere
        self.assertIn("pointerdown", js)
        css = self.url_open("/homeschool_practice/static/src/css/practice.css").text
        self.assertIn("--tap: 72px", css)

    def test_left_handed(self):
        self.student.practice_handedness = "left"
        self.authenticate("hs_learner", "hs_learner")
        self.assertIn('data-handedness="left"', self.url_open("/my/homeschool/practice").text)

    def test_manifest(self):
        r = self.url_open("/my/homeschool/practice/manifest.webmanifest")
        body = json.loads(r.text)
        self.assertEqual(body["display"], "standalone")
        self.assertEqual(body["start_url"], "/my/homeschool/practice")

    def test_only_the_learner(self):
        self.authenticate("hs_teacher", "hs_teacher")
        self.assertEqual(self.url_open("/my/homeschool/practice").status_code, 403)

    def test_link_on_portal_home(self):
        self.authenticate("hs_learner", "hs_learner")
        self.assertIn("/my/homeschool/practice", self.url_open("/my/homeschool").text)
