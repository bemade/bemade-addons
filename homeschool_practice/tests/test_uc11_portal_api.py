# -*- coding: utf-8 -*-
"""UC-11 — Portal JSON API (the contract every front end uses).

Acceptance criteria
-------------------
Routes under ``/my/homeschool/practice/api``, JSON, ``auth='user'``, the portal learner
only (a manager, a resource user or another learner gets an access error):

1. ``home`` → today's quests (startable in any order) with progress, goal progress
   (day / week / month), level, XP and XP to next level, badges earned (with the new
   ones flagged), **reward balances per type** (« en banque »), whether today is a
   rest day, handedness.
2. ``session/start {quest_id | deck_id, device, input_type, frontend}`` →
   ``session_id`` and the first item.
3. ``session/answer {session_id, item_id, given, hint_used, first_touch_ms, submit_ms,
   client_ts, client_uuid}`` → ``correct``, ``expected`` and ``hint`` (only when
   wrong), XP gained, ``level_up``, quests / goals / badges just completed, rewards
   just earned, and the next item or ``done``.
4. ``session/finish {session_id}`` → summary: answers given, correct answers, XP
   earned, quests and badges completed. **Never** which items are « known ».
5. **Forbidden in every payload** (checked recursively): latencies, thresholds,
   timers, time limits, mastery ``state``, ``box``, ``due_on``.
6. Item payload: ``item_id``, ``prompt``, ``answer_mode``, ``choices`` (ordered),
   ``answer``, ``intro`` and ``first_time``. The answer travels with the item so the screen
   shows right or wrong the instant he answers, without waiting for the network (owner,
   2026-11-13); the server still judges and records every answer.
7. Learner-facing strings come back in the learner's language (fr_CA tested).
"""
import json

from odoo.tests import tagged

from .common import PracticeHttpCase, API

FORBIDDEN = {"first_touch_ms", "submit_ms", "latency", "threshold", "timer", "time_limit", "state", "box",
             "due_on", "became_automatic", "outlier"}


@tagged("post_install", "-at_install")
class TestPortalApi(PracticeHttpCase):

    def assert_clean(self, payload, path="$"):
        if isinstance(payload, dict):
            for k, v in payload.items():
                self.assertNotIn(k, FORBIDDEN, "%s.%s leaks to the learner" % (path, k))
                self.assert_clean(v, "%s.%s" % (path, k))
        elif isinstance(payload, list):
            for i, v in enumerate(payload):
                self.assert_clean(v, "%s[%d]" % (path, i))

    def test_home(self):
        self.authenticate("hs_learner", "hs_learner")
        home = self.call("/home")
        self.assert_clean(home)
        for key in ("quests", "goals", "level", "xp", "xp_next_level", "balances", "badges", "rest_day", "handedness"):
            self.assertIn(key, home)
        self.assertEqual(len(home["quests"]), 3)
        self.assertEqual(home["balances"][0]["name"], "Temps de jeu")  # learner's language (fr_CA)
        self.assertEqual(home["labels"]["bank"], "En banque")
        self.assertEqual(home["handedness"], "right")

    def test_full_session(self):
        self.authenticate("hs_learner", "hs_learner")
        home = self.call("/home")
        quest = [q for q in home["quests"] if q["kind"] == "unit_session"][0]
        res = self.call("/session/start", quest_id=quest["id"], input_type="touch", device="iPad")
        self.assert_clean(res)
        item = res["item"]
        self.assertTrue(item["first_time"])
        self.assertTrue(item["intro"])
        sid, n, done = res["session_id"], 0, None
        while item and n < 40:
            answer = self.env["homeschool.practice.item"].browse(item["item_id"]).answer
            self.assertEqual(item["answer"], answer)
            given = answer if n != 1 else "999"
            out = self.call("/session/answer", session_id=sid, item_id=item["item_id"], given=given,
                            first_touch_ms=900, submit_ms=1400, client_ts="2026-11-16T14:00:00.000Z", client_uuid="u%s" % n)
            self.assert_clean(out)
            if given == "999":
                self.assertFalse(out["correct"])
                self.assertEqual(out["expected"], answer)
                self.assertIn("hint", out)
            else:
                self.assertNotIn("expected", out)
            self.assertGreater(out["xp"], 0)
            item = out.get("next")
            if n == 0:
                self.assertFalse(item["first_time"])
            done = out.get("done")
            n += 1
        self.assertTrue(done)
        self.assertGreaterEqual(out["summary"]["xp_session"], 1)
        self.assertNotIn("automatic", str(out["summary"]))
        session = self.env["homeschool.practice.session"].browse(sid)
        self.assertEqual(session.state, "done")
        self.assertEqual(session.attempt_ids[:1].first_touch_ms, 900)

    def test_replay_and_stale(self):
        self.authenticate("hs_learner", "hs_learner")
        self.call("/home")
        res = self.call("/session/start", deck_id=self.deck.id)
        item = res["item"]
        answer = self.env["homeschool.practice.item"].browse(item["item_id"]).answer
        a = self.call("/session/answer", session_id=res["session_id"], item_id=item["item_id"], given=answer, client_uuid="x")
        b = self.call("/session/answer", session_id=res["session_id"], item_id=item["item_id"], given=answer, client_uuid="x")
        self.assertEqual(self.env["homeschool.practice.attempt"].search_count([("session_id", "=", res["session_id"])]), 1)
        self.assertEqual(b.get("xp", 0), 0)

    def test_others_forbidden(self):
        self.authenticate("hs_teacher", "hs_teacher")
        self.assertDenied("/home")
        # another learner cannot touch this learner's session
        self.authenticate("hs_learner", "hs_learner")
        sid = self.call("/session/start", deck_id=self.deck.id)["session_id"]
        self.authenticate("hs_other", "hs_other")
        self.assertDenied("/session/finish", session_id=sid)

    def assertDenied(self, path, **params):
        r = self.url_open(API + path, data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
                          headers={"Content-Type": "application/json"})
        body = r.json()
        self.assertIn("error", body)
        self.assertNotIn("result", body)
        self.assertRegex(body["error"]["data"]["name"], "Forbidden|NotFound")
