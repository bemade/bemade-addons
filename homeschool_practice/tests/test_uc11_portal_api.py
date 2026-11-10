# -*- coding: utf-8 -*-
"""UC-11 — Portal JSON API (the contract every front end uses).

Acceptance criteria
-------------------
Routes under ``/my/homeschool/practice/api``, JSON, ``auth='user'``, the portal learner
only (a manager, a resource user or another learner gets 403):

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
   ``intro`` and ``first_time``; never the expected answer before it is answered.
7. Learner-facing strings come back in the learner's language (fr_CA tested).
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestPortalApi(HomeschoolCase):
    pass
