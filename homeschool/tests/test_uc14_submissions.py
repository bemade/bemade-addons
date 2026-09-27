# -*- coding: utf-8 -*-
"""UC-14 — Traces submitted from the portal, with a parent validation gate.

Acceptance criteria
-------------------
1. ``trace.submitted_by`` gains ``resource``; ``validated`` (default True for a
   parent-created trace, False when submitted by the student or a resource user),
   ``validated_by``, ``validated_at``. The importer's traces (parent) are validated.
2. A **portal user** may create a trace for a student he is related to; whatever he
   sends, the trace is stored ``diffusion=internal``, ``validated=False`` and
   ``submitted_by`` derived from his relation: own student → ``student``, resource
   user → ``resource``. Unrelated user, or another family's student → AccessError.
   Codes stay unique even though the submitter only sees a few traces.
3. The submitter sees his own pending (non-validated) traces; nobody else on the portal
   does. Portal users never write or unlink traces.
4. A **non-validated trace cannot be institutional** (ValidationError on create and write).
5. ``action_validate()`` (manager only) sets ``validated`` / ``validated_by`` /
   ``validated_at`` and may switch ``diffusion``; a portal user calling it gets an
   AccessError.
"""
from datetime import date

from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase


class TestSubmissions(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.portal = self.portal_user()
        self.student.user_id = self.portal
        self.teacher = self.resource_user(self.student)
        stranger_partner = self.env["res.partner"].create({"name": "Unrelated Person"})
        self.stranger = self.portal_user(partner=stranger_partner, login="hs_stranger")
        self.manager = self.manager_user()

    # ------------------------------------------------------------------
    # 1. parent traces are validated
    # ------------------------------------------------------------------
    def test_parent_trace_validated_by_default(self):
        t = self.Trace.with_user(self.manager).create({"name": "Parent trace", "student_id": self.student.id})
        self.assertEqual((t.submitted_by, t.validated, t.diffusion), ("parent", True, "internal"))
        self.assertFalse(t.validated_by or t.validated_at)
        t.write({"diffusion": "institutional"})  # fine: validated
        # the manager may record a trace the student handed over on paper: pending until validated
        s = self.Trace.with_user(self.manager).create({"name": "Handed over", "student_id": self.student.id, "submitted_by": "student"})
        self.assertFalse(s.validated)
        # the importer path is untouched: parent, validated
        imp = self.env["homeschool.importer"]
        imp.import_curriculum(self.repo)
        imp.import_traces(self.repo, self.student)
        imported = self.Trace.search([("student_id", "=", self.student.id), ("code", "like", "TR-2026-01-05-%")])
        self.assertEqual(len(imported), 2)
        self.assertTrue(all(imported.mapped("validated")))
        self.assertEqual(set(imported.mapped("submitted_by")), {"parent"})
        self.assertIn("institutional", imported.mapped("diffusion"))

    # ------------------------------------------------------------------
    # 2. portal submissions
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_student_submission_is_internal_and_pending(self):
        Trace = self.Trace.with_user(self.portal)
        self.assertTrue(Trace.has_access("create"))
        self.assertFalse(Trace.has_access("write") or Trace.has_access("unlink"))
        # a parent trace on the same day first: the student's code must not collide with it
        parent = self.Trace.create({"name": "Parent's", "student_id": self.student.id, "date": date(2026, 3, 2)})
        self.assertEqual(parent.code, "TR-2026-03-02-a")
        t = Trace.create({
            "name": "My drawing", "student_id": self.student.id, "date": date(2026, 3, 2),
            "diffusion": "institutional", "validated": True, "submitted_by": "parent",
            "validated_by": self.manager.id, "student_comment": "I liked it.",
        })
        self.assertEqual((t.submitted_by, t.validated, t.diffusion), ("student", False, "internal"))
        self.assertFalse(t.validated_by or t.validated_at)
        self.assertEqual(t.code, "TR-2026-03-02-b")
        self.assertEqual((t.student_id, t.company_id), (self.student, self.company))
        self.assertEqual(t.create_uid, self.portal)
        # a second one the same day: the next letter
        self.assertEqual(Trace.create({"name": "Another", "student_id": self.student.id, "date": date(2026, 3, 2)}).code, "TR-2026-03-02-c")
        # from a block: the block's defaults, still pending
        day = self.make_day(date(2026, 3, 3))
        block = self.make_block(day, "Segment", 45, 1, subject_id=self.fle.id)
        tb = Trace.with_context(default_block_id=block.id).create({"name": "From block"})
        self.assertEqual((tb.student_id, tb.block_id, tb.submitted_by, tb.validated), (self.student, block, "student", False))

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_resource_submission_and_refusals(self):
        t = self.Trace.with_user(self.teacher).create({"name": "Teacher's note", "student_id": self.student.id, "diffusion": "institutional"})
        self.assertEqual((t.submitted_by, t.validated, t.diffusion), ("resource", False, "internal"))
        self.assertEqual(t.company_id, self.company)
        # not attached to the second student
        with self.assertRaises(AccessError):
            self.Trace.with_user(self.teacher).create({"name": "Nope", "student_id": self.student_b.id})
        # the student cannot submit for another student
        with self.assertRaises(AccessError):
            self.Trace.with_user(self.portal).create({"name": "Nope", "student_id": self.student_b.id})
        # an unrelated portal user cannot submit at all
        with self.assertRaises(AccessError):
            self.Trace.with_user(self.stranger).create({"name": "Nope", "student_id": self.student.id})
        with self.assertRaises(AccessError):
            self.Trace.with_user(self.stranger).create({"name": "Nope"})
        self.assertFalse(self.Trace.search([("name", "=", "Nope")]))

    # ------------------------------------------------------------------
    # 3. who sees a pending trace
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_pending_trace_visible_to_its_submitter_only(self):
        institutional = self.Trace.create({"name": "Public", "student_id": self.student.id, "diffusion": "institutional"})
        internal = self.Trace.create({"name": "Private", "student_id": self.student.id})
        mine = self.Trace.with_user(self.portal).create({"name": "Mine", "student_id": self.student.id})
        theirs = self.Trace.with_user(self.teacher).create({"name": "Teacher's", "student_id": self.student.id})
        self.assertEqual(self.Trace.with_user(self.portal).search([]), (institutional | mine).with_user(self.portal))
        self.assertEqual(self.Trace.with_user(self.teacher).search([]), (institutional | theirs).with_user(self.teacher))
        mine.with_user(self.portal).read(["name", "validated", "submitted_by"])
        for rec in (internal, theirs):
            with self.assertRaises(AccessError):
                rec.with_user(self.portal).read(["name"])
        with self.assertRaises(AccessError):
            mine.with_user(self.teacher).read(["name"])
        # never write or unlink, not even his own pending trace
        with self.assertRaises(AccessError):
            mine.with_user(self.portal).write({"name": "Edited"})
        with self.assertRaises(AccessError):
            mine.with_user(self.portal).unlink()
        # the manager sees everything of his company
        self.assertIn(mine, self.Trace.with_user(self.manager).search([("validated", "=", False)]))
        self.assertIn(theirs, self.Trace.with_user(self.manager).search([("validated", "=", False)]))

    # ------------------------------------------------------------------
    # 4. non-validated → never institutional
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_unvalidated_cannot_be_institutional(self):
        pending = self.Trace.with_user(self.portal).create({"name": "Mine", "student_id": self.student.id})
        with self.assertRaises(ValidationError):
            pending.with_user(self.manager).write({"diffusion": "institutional"})
        self.assertEqual(pending.diffusion, "internal")
        with self.assertRaises(ValidationError):
            self.Trace.with_user(self.manager).create({"name": "X", "student_id": self.student.id, "submitted_by": "resource", "diffusion": "institutional"})
        with self.assertRaises(ValidationError):
            self.Trace.with_user(self.manager).create({"name": "X", "student_id": self.student.id, "validated": False, "diffusion": "institutional"})
        # un-validating an institutional trace is refused too
        public = self.Trace.with_user(self.manager).create({"name": "Public", "student_id": self.student.id, "diffusion": "institutional"})
        with self.assertRaises(ValidationError):
            public.write({"validated": False})

    # ------------------------------------------------------------------
    # 5. validation
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_validate(self):
        mine = self.Trace.with_user(self.portal).create({"name": "Mine", "student_id": self.student.id})
        theirs = self.Trace.with_user(self.teacher).create({"name": "Teacher's", "student_id": self.student.id})
        # the portal cannot validate, not even its own
        with self.assertRaises(AccessError):
            mine.with_user(self.portal).action_validate()
        with self.assertRaises(AccessError):
            theirs.with_user(self.teacher).action_validate()
        self.assertFalse(mine.validated or theirs.validated)
        # the manager validates
        mine.with_user(self.manager).action_validate()
        self.assertTrue(mine.validated)
        self.assertEqual(mine.validated_by, self.manager)
        self.assertTrue(mine.validated_at)
        self.assertEqual((mine.submitted_by, mine.diffusion), ("student", "internal"))
        mine.with_user(self.manager).write({"diffusion": "institutional"})  # allowed now
        # ... and may switch the diffusion in the same move
        theirs.with_user(self.manager).action_validate(diffusion="institutional")
        self.assertEqual((theirs.validated, theirs.diffusion, theirs.validated_by), (True, "institutional", self.manager))
        # validated traces leave the "pending" window: the submitter sees them only if institutional
        self.assertEqual(self.Trace.with_user(self.portal).search([]), mine.with_user(self.portal) | theirs.with_user(self.portal))
        still_internal = self.Trace.with_user(self.portal).create({"name": "Kept internal", "student_id": self.student.id})
        still_internal.with_user(self.manager).action_validate()
        self.assertNotIn(still_internal, self.Trace.with_user(self.portal).search([]))
        # a manager of another company cannot validate it
        manager_b = self.manager_user(self.company_b, login="hs_manager_b")
        pending = self.Trace.with_user(self.portal).create({"name": "Pending", "student_id": self.student.id})
        with self.assertRaises(AccessError):
            pending.with_user(manager_b).action_validate()
        self.assertFalse(pending.validated)
