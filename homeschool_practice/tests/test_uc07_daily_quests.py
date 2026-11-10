# -*- coding: utf-8 -*-
"""UC-07 — Daily quests: the app picks what needs practice, the learner picks the order.

Acceptance criteria
-------------------
1. ``homeschool.practice.quest.template``: ``name`` (translatable; may name the unit,
   e.g. « Une séance sur la table de 7 »), ``kind`` (``unit_session`` — finish a session
   on the unit that most needs practice; ``review_session`` — finish a review session;
   ``no_hint`` — N correct answers without a hint; ``perfect`` — a session without a
   miss; ``answers`` — N answers in a deck), ``target``, ``xp``, ``weight``,
   ``company_id``, ``active``.
2. ``homeschool.practice.quest``: one per learner, template and day; ``deck_id`` /
   ``unit_id`` when the quest targets one, ``progress``, ``done``, ``done_at``. Day
   boundary = the family's timezone.
3. **Drawn from need:** on the learner's first request of a practice day the server
   draws the day's quests (default 3, per learner): the unit with the most due or
   newly introduced items gets a ``unit_session`` quest; a ``review_session`` when
   other unlocked units have due items; the rest from the pool, weighted, never the
   same template twice in a day. Idempotent for the day.
4. **The learner chooses the order**: every quest of the day is startable at any time,
   in any order; a session quest starts its session from the quest.
5. Progress counts only that day's events; an unfinished quest ends with the day — no
   penalty, no message.
6. **Cap**: once the day's quests are done, more practice still earns XP and badges
   but no more quests or goal progress that day.
7. **Practice days are configured per learner** (weekdays, default Monday–Friday).
   On other days no quests are drawn and the screen says it is a rest day; free
   practice stays possible and earns XP.
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestDailyQuests(HomeschoolCase):
    pass
