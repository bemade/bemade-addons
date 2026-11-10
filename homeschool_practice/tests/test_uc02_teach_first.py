# -*- coding: utf-8 -*-
"""UC-02 — Teach first: a parent unlocks a unit; progression inside it is automatic.

Acceptance criteria
-------------------
1. ``homeschool.practice.unit.access`` (one per learner and unit): ``state``
   (``locked`` | ``unlocked``), ``unlocked_on``, ``unlocked_by``. Every unit starts
   locked; items of a locked unit are **never** scheduled.
2. **Unlocking is a parent decision, by unit** (a whole times table, a whole grammar
   concept): ``unit.action_unlock(student)``, idempotent (keeps the first date).
   Re-locking takes the unit out of scheduling and keeps its history.
3. **Progression inside an unlocked unit is automatic**: at unlock only the first
   ``step`` group is introduced (e.g. × 0 to × 5); the next item is introduced when
   the items already introduced are mostly secure (default: ≥ 80 % in box 3 or more).
   No parent action, no learner action.
4. The first time a unit is served, the payload carries its ``intro`` and
   ``first_time = True``; afterwards not.
5. A portal learner cannot unlock or lock anything (AccessError).
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestTeachFirst(HomeschoolCase):
    pass
