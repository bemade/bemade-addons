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
from odoo import fields
from odoo.exceptions import AccessError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase

MODELS = [
    "homeschool.student", "homeschool.year", "homeschool.subject", "homeschool.item", "homeschool.item.dependency",
    "homeschool.project", "homeschool.day", "homeschool.block", "homeschool.block.template", "homeschool.material",
    "homeschool.trace", "homeschool.indicator", "homeschool.indicator.value", "homeschool.journal", "homeschool.review",
]
NO_PORTAL = ["homeschool.journal", "homeschool.indicator", "homeschool.indicator.value", "homeschool.review"]


class TestAccess(HomeschoolCase):
    def test_manager_full_access(self):
        manager = self.manager_user()
        for model in MODELS:
            Model = self.env[model].with_user(manager)
            for op in ("read", "write", "create", "unlink"):
                self.assertTrue(Model.has_access(op), "%s should be %s-able by the manager" % (model, op))
        day = self.Day.with_user(manager).create({"student_id": self.student.id, "date": fields.Date.context_today(self.Day)})
        self.env["homeschool.journal"].with_user(manager).create({"day_id": day.id, "went_well": "ok"})

    @mute_logger("odoo.addons.base.models.ir_model")
    def test_plain_internal_user_no_access(self):
        plain = self.internal_user()
        for model in MODELS:
            self.assertFalse(self.env[model].with_user(plain).has_access("read"), model)
        with self.assertRaises(AccessError):
            self.Item.with_user(plain).search([])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_portal_rules_by_diffusion(self):
        Rule = self.env["ir.rule"]
        portal_group = self.env.ref("base.group_portal")
        for model in ("homeschool.trace", "homeschool.material"):
            rules = Rule.search([("model_id.model", "=", model), ("groups", "in", portal_group.id)])
            self.assertEqual(len(rules), 1, model)
            self.assertIn("institutional", rules.domain_force)
            self.assertTrue(rules.perm_read)
            self.assertFalse(rules.perm_write or rules.perm_create or rules.perm_unlink)
        for model in ("homeschool.day", "homeschool.block"):
            rules = Rule.search([("model_id.model", "=", model), ("groups", "in", portal_group.id)])
            self.assertEqual(len(rules), 1, model)
            self.assertIn("student_id.user_id", rules.domain_force)
        # this module alone ships no portal access line: everything is refused
        portal = self.portal_user()
        self.student.user_id = portal
        for model in MODELS:
            self.assertFalse(self.env[model].with_user(portal).has_access("read"), model)
        trace = self.Trace.create({"name": "Public", "student_id": self.student.id, "diffusion": "institutional"})
        with self.assertRaises(AccessError):
            trace.with_user(portal).read(["name"])

    def test_no_portal_rule_on_journal_indicators_reviews(self):
        portal_group = self.env.ref("base.group_portal")
        for model in NO_PORTAL:
            self.assertFalse(self.env["ir.rule"].search([("model_id.model", "=", model)]), "%s must have no rule at all" % model)
            self.assertFalse(self.env["ir.model.access"].search([("model_id.model", "=", model), ("group_id", "=", portal_group.id)]), model)
            self.assertFalse(self.env["ir.model.access"].search([("model_id.model", "=", model), ("group_id", "=", False)]), "%s: no global access line" % model)

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.addons.base.models.ir_attachment")
    def test_internal_attachment_hidden_from_portal(self):
        portal = self.portal_user()
        self.student.user_id = portal
        trace = self.Trace.create({"name": "Private", "student_id": self.student.id, "diffusion": "internal"})
        att = self.env["ir.attachment"].create({"name": "secret.pdf", "raw": b"%PDF-1.4 secret", "res_model": "homeschool.trace", "res_id": trace.id})
        trace.attachment_ids |= att
        with self.assertRaises(AccessError):
            att.with_user(portal).read(["datas"])
