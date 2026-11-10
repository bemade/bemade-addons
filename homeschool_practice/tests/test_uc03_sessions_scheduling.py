# -*- coding: utf-8 -*-
"""UC-03 — Sessions and scheduling (spaced repetition).

Acceptance criteria
-------------------
1. ``homeschool.practice.session``: ``student_id``, ``deck_id``, ``quest_id`` (the quest
   it was started from, UC-07), ``kind`` (``unit`` — focus on one unit; ``review`` —
   items of every unlocked unit of the deck), ``unit_id``, ``started_at``,
   ``ended_at``, ``state`` (``open`` | ``done`` | ``abandoned``), ``device``,
   ``input_type`` (``touch`` | ``mouse`` | ``keyboard``), ``frontend``, ``attempt_ids``.
   Starting a session abandons the learner's other open session.
2. **A session is a number of items, not a duration** (``deck.session_size``). Nothing
   in the session or its payload is a time limit.
3. ``unit`` session: due items of the unit first (Leitner intervals 0, 1, 3, 7, 14 days,
   configurable on the deck), most overdue first; then newly introduced items (at most
   3 per session); then about 1 in 5 review items **from other unlocked units** of the
   deck.
4. ``review`` session: due items across every unlocked unit of the deck, most overdue
   first, then the least recently seen.
5. Locked units are never served; introduced-only items are (UC-02 §3).
6. A missed item comes back later in the same session (after at least two others) and
   goes back to box 1.
7. The session **ends on a correct answer**: after a miss on the last planned item, one
   more already-secure item is served.
8. Fewer eligible items than ``session_size`` → a shorter session, never padded.
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestSessionsScheduling(HomeschoolCase):
    pass
