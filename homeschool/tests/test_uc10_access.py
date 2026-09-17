# -*- coding: utf-8 -*-
"""UC-10 — Access: the manager sees everything; portal rules by diffusion; the
journal and indicators have no portal rule at all.

Acceptance criteria
-------------------
1. ``homeschool.group_homeschool_manager`` (implies base.group_user) has full CRUD on
   every homeschool model.
2. A plain internal user (base.group_user only) has **no** access to homeschool models.
3. Record rules exist for ``base.group_portal`` on ``homeschool.trace`` and
   ``homeschool.material`` limited to ``diffusion = institutional`` **read-only**,
   and on ``homeschool.block`` / ``homeschool.day`` read-only for the student's own
   records — but no ``ir.model.access`` for portal is shipped by this module: the
   rules only take effect when ``homeschool_portal`` grants the access lines. This
   module alone: a portal user gets AccessError everywhere.
4. There is **no** rule and no access line for portal on ``homeschool.journal``,
   ``homeschool.indicator``, ``homeschool.indicator.value`` and ``homeschool.review``;
   a test asserts none exists (guards against a future module adding one by mistake).
5. Attachments of an internal trace are not readable by a portal user even by id.
"""
from .common import HomeschoolCase


class TestAccess(HomeschoolCase):
    def test_manager_full_access(self):
        self.skipTest("pending — TDD")

    def test_plain_internal_user_no_access(self):
        self.skipTest("pending — TDD")

    def test_portal_rules_by_diffusion(self):
        self.skipTest("pending — TDD")

    def test_no_portal_rule_on_journal_indicators_reviews(self):
        self.skipTest("pending — TDD")

    def test_internal_attachment_hidden_from_portal(self):
        self.skipTest("pending — TDD")
