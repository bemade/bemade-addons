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
   work done, not for speed or for « knowing »). Celebrations earned during a lesson are
   held and shown at the end of the lesson (or when he leaves it), never mid-lesson.
5. Touch targets ≥ 64 px; zoom gestures disabled on the page; a web-app manifest so it
   can be added to the iPad home screen and open full screen. Target: Safari on
   iPadOS 17 and later.
6. Answers not yet sent (no network) are queued on the device and sent in order when
   the connection returns (each with its ``client_uuid``).
7. The script and stylesheet URLs carry a hash of their content, so a code change
   reaches an iPad running it from the home screen without a version bump.
8. Rendering is checked by HttpCase tests; real touch behaviour is checked by hand on
   the iPad before release (noted in the review artifact).
9. Every tap on the number pad counts: a key acts as the finger lands (``pointerdown``),
   not on the browser's ``click``, which iOS drops when the finger slides a little or
   the next finger lands before the previous one lifts (fast typing). The answer area
   never starts a scroll or a pan (``touch-action: none``). Answer buttons act the same way.
10. Right or wrong shows the instant he answers, judged on the device with the server's
    rule (the item carries its answer): the picked button turns green or red and, on a
    miss, the right one lights up. The next item comes with the server's reply, while the
    feedback is on screen.
11. On a choices unit (grammar), after 2 misses in a row in the same unit during a
    lesson, the next card of that unit shows its trick on the card before he answers,
    and the answer buttons come in a moment later; the answer is recorded as hint used.
    It stops once he gets one right in that unit.
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
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertNotIn("&lt;!DOCTYPE", html)
        self.assertIn("practice.js?v=", html)
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

    def test_celebrations_held_to_end_of_lesson(self):
        js = self.url_open("/homeschool_practice/static/src/js/practice.js").text
        feedback = js[js.index("function feedback("):js.index("function hold(")]
        self.assertNotIn("celebrate(", feedback)
        self.assertIn("hold(eventsToCelebrations(res))", feedback)
        self.assertIn("release()", js[js.index("function summary("):js.index("function finish(")])
        self.assertIn("release()", js[js.index("function quit("):])

    def test_keypad_acts_on_touch_down(self):
        js = self.url_open("/homeschool_practice/static/src/js/practice.js").text
        show = js[js.index("function showItem("):js.index("function key(")]
        self.assertIn('querySelectorAll("[data-key]")', show)
        keys = show[show.index('querySelectorAll("[data-key]")'):show.index('querySelectorAll("[data-choice]")')]
        self.assertIn('"pointerdown"', keys)
        self.assertNotIn('"click"', keys)
        css = self.url_open("/homeschool_practice/static/src/css/practice.css").text
        self.assertRegex(css, r"\.hp-input\s*\{[^}]*touch-action:\s*none")

    def test_asset_version_follows_content(self):
        from odoo.addons.homeschool_practice.controllers.portal import asset_version
        self.authenticate("hs_learner", "hs_learner")
        html = self.url_open("/my/homeschool/practice").text
        self.assertIn("practice.js?v=%s" % asset_version(), html)
        self.assertIn("practice.css?v=%s" % asset_version(), html)
        self.assertRegex(asset_version(), r"^[0-9a-f]{12}$")

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

    def test_instant_feedback_and_trick(self):
        js = self.url_open("/homeschool_practice/static/src/js/practice.js").text
        self.assertIn("function judge(item, given)", js)
        self.assertRegex(js, r'\[data-choice\]"\)\.forEach\(function \(b\) \{\s*b\.addEventListener\("pointerdown"')
        self.assertIn("var TRICK_AFTER = 2;", js)
        self.assertIn('class="hp-trick"', js)
        self.assertIn("state.hintUsed = true; }", js)
        css = self.url_open("/homeschool_practice/static/src/css/practice.css").text
        for cls in (".hp-choice.is-right", ".hp-choice.is-wrong", ".hp-trick", ".hp-choices.is-waiting"):
            self.assertIn(cls, css)
