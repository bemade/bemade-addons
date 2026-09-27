# -*- coding: utf-8 -*-
"""UC-10 — Access: one instance, several families. Managers are scoped by company;
portal users see their own student (or the students they are attached to as resource
users); the journal, indicators and reviews have no portal access at all.

Acceptance criteria
-------------------
1. ``homeschool.group_homeschool_manager`` (implies base.group_user) has full CRUD on
   every homeschool model — **within the companies the user is attached to**: a manager
   of company B gets an AccessError on every family-owned record of company A (student,
   year, day, block, trace, review, project, material, block template, indicator,
   indicator value, journal, item coverage) and never sees them in a search. Curriculum items, item
   dependencies and subjects are shared (company-less) and visible to every manager.
2. A plain internal user (base.group_user only) has **no** access to homeschool models.
3. Portal access is read-only and limited to day, block, trace and material:
   - a portal student (``student.user_id``) sees his own days and blocks only;
   - a resource user (``student.resource_user_ids``, portal users only) sees the days
     and blocks of the students he is attached to, and only the **institutional**
     traces and material of the companies of those students;
   - internal traces/material are never readable by portal, even by id.
4. There is **no** portal rule, no portal access line and no global access line on
   ``homeschool.journal``, ``homeschool.indicator``, ``homeschool.indicator.value`` and
   ``homeschool.review``; their only rules are the manager company rules (a test asserts
   this, guarding against a future module adding a portal rule by mistake).
5. Attachments of an internal trace are not readable by a portal user even by id.
6. ``student.resource_user_ids`` refuses internal (non-share) users.
"""
from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase

MODELS = [
    "homeschool.student", "homeschool.year", "homeschool.subject", "homeschool.item", "homeschool.item.dependency",
    "homeschool.project", "homeschool.day", "homeschool.block", "homeschool.block.template", "homeschool.material",
    "homeschool.trace", "homeschool.indicator", "homeschool.indicator.value", "homeschool.journal", "homeschool.review",
    "homeschool.item.coverage", "homeschool.deliverable", "homeschool.reading.book", "homeschool.reading.entry",
]
FAMILY_MODELS = [
    "homeschool.student", "homeschool.year", "homeschool.day", "homeschool.block", "homeschool.trace",
    "homeschool.review", "homeschool.project", "homeschool.material", "homeschool.block.template",
    "homeschool.indicator", "homeschool.indicator.value", "homeschool.journal", "homeschool.item.coverage",
]
SHARED_MODELS = ["homeschool.subject", "homeschool.item", "homeschool.item.dependency"]
PORTAL_READ = ["homeschool.day", "homeschool.block", "homeschool.trace", "homeschool.material"]
# the portal access lines (read, write, create, unlink) per model — UC-12..14 added the last four
PORTAL_ACCESS = {
    "homeschool.day": (1, 0, 0, 0), "homeschool.block": (1, 0, 0, 0), "homeschool.material": (1, 0, 0, 0),
    "homeschool.trace": (1, 0, 1, 0), "homeschool.deliverable": (1, 1, 0, 0),
    "homeschool.reading.book": (1, 0, 0, 0), "homeschool.reading.entry": (1, 1, 1, 0),
}
NO_PORTAL = ["homeschool.journal", "homeschool.indicator", "homeschool.indicator.value", "homeschool.review"]


class TestAccess(HomeschoolCase):
    def _family_records(self, student):
        """One record of every family model, all belonging to ``student``'s company."""
        env = self.env(context=dict(self.env.context, allowed_company_ids=student.company_id.ids))
        day = env["homeschool.day"].create({"student_id": student.id, "date": fields.Date.context_today(self.Day)})
        block = env["homeschool.block"].create({"day_id": day.id, "name": "A block", "duration_planned": 30})
        trace = env["homeschool.trace"].create({"name": "A trace", "student_id": student.id, "diffusion": "institutional"})
        review = env["homeschool.review"].create({"student_id": student.id})
        project = env["homeschool.project"].create({"code": "P-%d" % student.id, "name": "A project", "student_id": student.id})
        material = env["homeschool.material"].create({"name": "A fiche", "diffusion": "institutional"})
        template = env["homeschool.block.template"].create({"student_id": student.id, "weekday": "0", "name": "Segment"})
        indicator = env["homeschool.indicator"].create({"code": "IND-%d" % student.id, "name": "An indicator"})
        value = env["homeschool.indicator.value"].create({"indicator_id": indicator.id, "student_id": student.id, "value": 1.0})
        journal = env["homeschool.journal"].create({"day_id": day.id, "went_well": "ok"})
        coverage = env["homeschool.item.coverage"].create({"item_id": self.item_fle.id})
        records = [student, student.year_ids[:1], day, block, trace, review, project, material, template, indicator, value, journal, coverage]
        self.assertEqual([r._name for r in records], FAMILY_MODELS)
        for rec in records:
            self.assertEqual(rec.company_id, student.company_id, rec._name)
        return records

    # ------------------------------------------------------------------
    # 1. managers, by company
    # ------------------------------------------------------------------
    def test_manager_full_access(self):
        manager = self.manager_user()
        for model in MODELS:
            Model = self.env[model].with_user(manager)
            for op in ("read", "write", "create", "unlink"):
                self.assertTrue(Model.has_access(op), "%s should be %s-able by the manager" % (model, op))
        day = self.Day.with_user(manager).create({"student_id": self.student.id, "date": fields.Date.context_today(self.Day)})
        self.env["homeschool.journal"].with_user(manager).create({"day_id": day.id, "went_well": "ok"})
        self.assertEqual(day.company_id, self.company)

    @mute_logger("odoo.addons.base.models.ir_rule")
    def test_manager_cross_company_denied(self):
        records_a = self._family_records(self.student)
        records_b = self._family_records(self.student_b)
        manager_b = self.manager_user(self.company_b, login="hs_manager_b")
        for rec_a, rec_b in zip(records_a, records_b):
            Model = self.env[rec_a._name].with_user(manager_b)
            # search: only B's rows, never A's
            found = Model.search([("id", "in", (rec_a | rec_b).ids)])
            self.assertEqual(found, rec_b.with_user(manager_b), "%s: manager B must see B's record only" % rec_a._name)
            # by id: AccessError on A, fine on B
            with self.assertRaises(AccessError, msg=rec_a._name):
                rec_a.with_user(manager_b).read(["id"])
            rec_b.with_user(manager_b).read(["id"])
            with self.assertRaises(AccessError, msg=rec_a._name):
                rec_a.with_user(manager_b).write({"company_id": self.company_b.id})
        # the curriculum is shared: every manager reads it
        for model in SHARED_MODELS:
            self.assertTrue(self.env[model].with_user(manager_b).has_access("read"), model)
        self.assertIn(self.item_fle, self.Item.with_user(manager_b).search([]))

    def test_company_defaults_follow_the_student(self):
        """Records created from a student of company B land in company B even from the main company."""
        day = self.Day._get_or_create(self.student_b, fields.Date.context_today(self.Day))
        self.assertEqual(day.company_id, self.company_b)
        block = self.Block.create({"day_id": day.id, "name": "B"})
        self.assertEqual(block.company_id, self.company_b)
        journal = self.env["homeschool.journal"].create({"day_id": day.id, "went_well": "ok"})
        self.assertEqual(journal.company_id, self.company_b)
        trace = self.Trace.with_context(default_block_id=block.id).create({"name": "From block"})
        self.assertEqual((trace.company_id, trace.student_id), (self.company_b, self.student_b))

    # ------------------------------------------------------------------
    # 2. plain internal user
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model")
    def test_plain_internal_user_no_access(self):
        plain = self.internal_user()
        for model in MODELS:
            self.assertFalse(self.env[model].with_user(plain).has_access("read"), model)
        with self.assertRaises(AccessError):
            self.Item.with_user(plain).search([])

    # ------------------------------------------------------------------
    # 3. portal: own student, resource users
    # ------------------------------------------------------------------
    def test_portal_rules_shape(self):
        Rule = self.env["ir.rule"]
        portal_group = self.env.ref("base.group_portal")
        rules = Rule.search([("model_id.model", "=", "homeschool.material"), ("groups", "in", portal_group.id)])
        self.assertEqual(len(rules), 1)
        self.assertIn("institutional", rules.domain_force)
        self.assertIn("resource_user_ids", rules.domain_force)
        self.assertTrue(rules.perm_read)
        self.assertFalse(rules.perm_write or rules.perm_create or rules.perm_unlink)
        # traces: the institutional read rule, plus the submitter's own pending traces (read + create)
        rules = Rule.search([("model_id.model", "=", "homeschool.trace"), ("groups", "in", portal_group.id)])
        self.assertEqual(len(rules), 2)
        institutional = rules.filtered(lambda r: "institutional" in r.domain_force)
        own = rules - institutional
        self.assertIn("resource_user_ids", institutional.domain_force)
        self.assertTrue(institutional.perm_read)
        self.assertFalse(institutional.perm_write or institutional.perm_create or institutional.perm_unlink)
        self.assertIn("create_uid", own.domain_force)
        self.assertIn("'validated', '=', False", own.domain_force)
        self.assertTrue(own.perm_read and own.perm_create)
        self.assertFalse(own.perm_write or own.perm_unlink)
        for model in ("homeschool.day", "homeschool.block", "homeschool.reading.book"):
            rules = Rule.search([("model_id.model", "=", model), ("groups", "in", portal_group.id)])
            self.assertEqual(len(rules), 1, model)
            self.assertIn("student_id.user_id", rules.domain_force)
            self.assertIn("resource_user_ids", rules.domain_force)
            self.assertTrue(rules.perm_read)
            self.assertFalse(rules.perm_write or rules.perm_create or rules.perm_unlink)
        # deliverables and reading entries: a read rule (own or resource) and a write rule (own student only)
        for model, creates in (("homeschool.deliverable", False), ("homeschool.reading.entry", True)):
            rules = Rule.search([("model_id.model", "=", model), ("groups", "in", portal_group.id)])
            self.assertEqual(len(rules), 2, model)
            read = rules.filtered("perm_read")
            write = rules - read
            self.assertIn("resource_user_ids", read.domain_force)
            self.assertFalse(read.perm_write or read.perm_create or read.perm_unlink)
            self.assertNotIn("resource_user_ids", write.domain_force)
            self.assertIn("student_id.user_id", write.domain_force)
            self.assertTrue(write.perm_write)
            self.assertEqual(bool(write.perm_create), creates)
            self.assertFalse(write.perm_unlink)
        # access lines: exactly the portal surface above, nothing else; never unlink
        for model in MODELS:
            lines = self.env["ir.model.access"].search([("model_id.model", "=", model), ("group_id", "=", portal_group.id)])
            if model in PORTAL_ACCESS:
                self.assertEqual(len(lines), 1, model)
                self.assertEqual((lines.perm_read, lines.perm_write, lines.perm_create, lines.perm_unlink),
                                 tuple(bool(p) for p in PORTAL_ACCESS[model]), model)
            else:
                self.assertFalse(lines, "%s: no portal access line" % model)

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_portal_student_sees_own_days_and_blocks(self):
        records_a = self._family_records(self.student)
        records_b = self._family_records(self.student_b)
        day_a, block_a = records_a[2], records_a[3]
        day_b, block_b = records_b[2], records_b[3]
        portal = self.portal_user()
        self.student.user_id = portal
        for model in PORTAL_READ:
            self.assertTrue(self.env[model].with_user(portal).has_access("read"), model)
            self.assertFalse(self.env[model].with_user(portal).has_access("write"), model)
        self.assertEqual(self.Day.with_user(portal).search([]), day_a.with_user(portal))
        self.assertEqual(self.Block.with_user(portal).search([]), block_a.with_user(portal))
        day_a.with_user(portal).read(["name", "student_id"])
        block_a.with_user(portal).read(["name", "start_time"])
        with self.assertRaises(AccessError):
            day_b.with_user(portal).read(["name"])
        with self.assertRaises(AccessError):
            block_b.with_user(portal).read(["name"])
        with self.assertRaises(AccessError):
            day_a.with_user(portal).write({"note": "no"})
        # the student's own institutional trace / material: yes; the other family's: no
        trace_a, material_a = records_a[4], records_a[7]
        trace_b, material_b = records_b[4], records_b[7]
        self.assertEqual(self.Trace.with_user(portal).search([]), trace_a.with_user(portal))
        self.assertEqual(self.env["homeschool.material"].with_user(portal).search([]), material_a.with_user(portal))
        with self.assertRaises(AccessError):
            trace_b.with_user(portal).read(["name"])
        with self.assertRaises(AccessError):
            material_b.with_user(portal).read(["name"])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_resource_user_sees_attached_student_only(self):
        records_a = self._family_records(self.student)
        records_b = self._family_records(self.student_b)
        day_a, block_a, trace_a, material_a = records_a[2], records_a[3], records_a[4], records_a[7]
        day_b, block_b, trace_b, material_b = records_b[2], records_b[3], records_b[4], records_b[7]
        internal_trace_a = self.Trace.create({"name": "Private", "student_id": self.student.id, "diffusion": "internal"})
        internal_material_a = self.env["homeschool.material"].create({"name": "Private fiche", "diffusion": "internal"})
        teacher = self.resource_user(self.student)
        self.assertIn(teacher, self.student.resource_user_ids)
        self.assertNotIn(teacher, self.student_b.resource_user_ids)
        # days and blocks of the attached student
        self.assertEqual(self.Day.with_user(teacher).search([]), day_a.with_user(teacher))
        self.assertEqual(self.Block.with_user(teacher).search([]), block_a.with_user(teacher))
        with self.assertRaises(AccessError):
            day_b.with_user(teacher).read(["name"])
        with self.assertRaises(AccessError):
            block_b.with_user(teacher).read(["name"])
        # institutional traces / material of that student's company only
        self.assertEqual(self.Trace.with_user(teacher).search([]), trace_a.with_user(teacher))
        self.assertEqual(self.env["homeschool.material"].with_user(teacher).search([]), material_a.with_user(teacher))
        for rec in (trace_b, material_b, internal_trace_a, internal_material_a):
            with self.assertRaises(AccessError, msg=rec.display_name):
                rec.with_user(teacher).read(["name"])
        # read-only
        with self.assertRaises(AccessError):
            trace_a.with_user(teacher).write({"name": "x"})
        # attached to both students: sees both families
        self.student_b.resource_user_ids = [fields.Command.link(teacher.id)]
        self.assertEqual(self.Day.with_user(teacher).search([]), (day_a | day_b).with_user(teacher))
        self.assertEqual(self.Trace.with_user(teacher).search([]), (trace_a | trace_b).with_user(teacher))
        # detached: sees nothing
        (self.student | self.student_b).write({"resource_user_ids": [fields.Command.clear()]})
        self.assertFalse(self.Day.with_user(teacher).search([]))
        self.assertFalse(self.Trace.with_user(teacher).search([]))

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_portal_never_reaches_journal_indicators_reviews(self):
        self._family_records(self.student)
        portal = self.portal_user()
        self.student.user_id = portal
        teacher = self.resource_user(self.student)
        for user in (portal, teacher):
            for model in NO_PORTAL + ["homeschool.student", "homeschool.year", "homeschool.project", "homeschool.block.template"]:
                self.assertFalse(self.env[model].with_user(user).has_access("read"), "%s / %s" % (user.login, model))
                with self.assertRaises(AccessError):
                    self.env[model].with_user(user).search([])

    # ------------------------------------------------------------------
    # 4. nothing for portal on journal / indicators / reviews
    # ------------------------------------------------------------------
    def test_no_portal_rule_on_journal_indicators_reviews(self):
        portal_group = self.env.ref("base.group_portal")
        manager_group = self.env.ref("homeschool.group_homeschool_manager")
        for model in NO_PORTAL:
            rules = self.env["ir.rule"].search([("model_id.model", "=", model)])
            self.assertTrue(rules, "%s: the manager company rule must exist" % model)
            for rule in rules:
                self.assertEqual(rule.groups, manager_group, "%s: only manager rules (no portal, no global rule)" % model)
            self.assertFalse(self.env["ir.model.access"].search([("model_id.model", "=", model), ("group_id", "=", portal_group.id)]), model)
            self.assertFalse(self.env["ir.model.access"].search([("model_id.model", "=", model), ("group_id", "=", False)]), "%s: no global access line" % model)

    # ------------------------------------------------------------------
    # 5. attachments
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule", "odoo.addons.base.models.ir_attachment")
    def test_internal_attachment_hidden_from_portal(self):
        portal = self.portal_user()
        self.student.user_id = portal
        trace = self.Trace.create({"name": "Private", "student_id": self.student.id, "diffusion": "internal"})
        att = self.env["ir.attachment"].create({"name": "secret.pdf", "raw": b"%PDF-1.4 secret", "res_model": "homeschool.trace", "res_id": trace.id})
        trace.attachment_ids |= att
        with self.assertRaises(AccessError):
            att.with_user(portal).read(["datas"])

    # ------------------------------------------------------------------
    # 6. resource users are portal users
    # ------------------------------------------------------------------
    def test_resource_users_must_be_portal(self):
        internal = self.internal_user()
        with self.assertRaises(ValidationError):
            self.student.resource_user_ids = [fields.Command.link(internal.id)]
        manager = self.manager_user()
        with self.assertRaises(ValidationError):
            self.student.resource_user_ids = [fields.Command.link(manager.id)]
        teacher = self.resource_user()
        self.student.resource_user_ids = [fields.Command.link(teacher.id)]
        self.assertEqual(self.student.resource_user_ids, teacher)
