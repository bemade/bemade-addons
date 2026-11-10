# -*- coding: utf-8 -*-
"""UC-10 — Access: learners, educators, families.

Acceptance criteria
-------------------
1. A **portal learner** reaches his own practice only through the portal API (UC-11):
   decks, his quests, goals, XP, level, badges and reward balances. Direct ORM reads of
   sessions, attempts and mastery as the learner → AccessError; another learner's data
   → AccessError; no unlink anywhere.
2. **Resource users** (the outside teacher, attached to the student) read all practice
   data of their students, timing and mastery included, and write nothing. Reward
   ledgers: not visible to them.
3. **Managers** see and manage the records of their companies only.
4. Reward ledger lines are created by the system (goals) or by managers (redemptions,
   adjustments); a learner or a resource user cannot create or alter them.
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestAccess(HomeschoolCase):
    pass
