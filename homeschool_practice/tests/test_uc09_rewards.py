# -*- coding: utf-8 -*-
"""UC-09 — Family-defined rewards: earned by goals, never expire.

Acceptance criteria
-------------------
1. ``homeschool.reward.type``: ``name`` (e.g. « Temps de jeu »), ``unit`` (e.g.
   « min », « $ »), ``company_id``, ``active``. Families create their own; the module
   ships none active by default.
2. ``homeschool.reward.rule``: ``student_id``, ``goal_period`` (day / week / month),
   ``reward_type_id``, ``amount`` (> 0), ``date_from``. Several rules may pay for one
   goal (e.g. a week pays minutes AND credit). A new rule from a date replaces the
   previous one for later achievements only.
3. ``homeschool.reward.ledger``: append-only; ``student_id``, ``reward_type_id``,
   ``kind`` (``earned`` | ``redeemed`` | ``adjustment``), ``amount`` (signed),
   ``date``, ``source`` (the goal achievement, or the redemption), ``note``,
   ``recorded_by``. A goal achievement writes one ``earned`` line per applicable rule,
   **with the amount of the rule in force at that moment**, once (idempotent).
4. **No expiry:** there is no expiry field or cron; a balance earned months ago is
   still whole.
5. ``student.reward_balance_ids`` (per type) = sum of the ledger. A redemption is
   recorded by a manager (``action_redeem(type, amount, note)``) and cannot take a
   balance below zero (UserError).
6. XP never appears in the ledger, and no ledger line is created from XP.
7. Rewards of one family are never visible to another (company rules).
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestRewards(HomeschoolCase):
    pass
