# -*- coding: utf-8 -*-
"""UC-12 — Deliverables: the paper « liste du jour » as data, tickable by the student.

Acceptance criteria
-------------------
1. ``homeschool.deliverable`` is bound to a day (``day_id``, cascade); ``student_id`` and
   ``company_id`` follow the day, so several students and several families never mix.
   Fields: ``sequence``, ``name``, ``detail``, ``when`` ("9 h", "bonus"), ``bonus``,
   ``done``, ``done_at``, ``done_by``. ``day.deliverable_ids`` lists them in order.
2. Flipping ``done`` stamps ``done_at`` / ``done_by`` with the user who ticked; unticking
   clears both.
3. A **portal student** (``student.user_id``) sees his own deliverables and may change
   ``done`` and nothing else: any other field in the write → AccessError; another
   student's deliverable → AccessError; create and unlink → AccessError.
4. A **resource user** reads the deliverables of the students he is attached to and
   cannot write at all.
5. The manager edits every field.
"""
from datetime import date

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase


class TestDeliverables(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.day = self.make_day(date(2026, 3, 2))
        self.day_b = self.Day.create({"student_id": self.student_b.id, "date": date(2026, 3, 2)})
        self.d1 = self.Deliverable.create({"day_id": self.day.id, "name": "Copy the sentence", "when": "9 h", "sequence": 1})
        self.d2 = self.Deliverable.create({"day_id": self.day.id, "name": "Time worksheet", "when": "10 h", "sequence": 2, "detail": "Two pages"})
        self.d_bonus = self.Deliverable.create({"day_id": self.day.id, "name": "Extra reading", "when": "bonus", "bonus": True, "sequence": 3})
        self.d_b = self.Deliverable.create({"day_id": self.day_b.id, "name": "Other family's task"})

    # ------------------------------------------------------------------
    # 1. day-bound, family-bound
    # ------------------------------------------------------------------
    def test_day_bound_fields(self):
        self.assertEqual(self.day.deliverable_ids, self.d1 | self.d2 | self.d_bonus)
        self.assertEqual([d.name for d in self.day.deliverable_ids], ["Copy the sentence", "Time worksheet", "Extra reading"])
        for d in self.day.deliverable_ids:
            self.assertEqual((d.student_id, d.company_id), (self.student, self.company))
            self.assertFalse(d.done or d.done_at or d.done_by)
        self.assertEqual((self.d_b.student_id, self.d_b.company_id), (self.student_b, self.company_b))
        self.assertTrue(self.d_bonus.bonus)
        # created inline from the day form
        self.day.write({"deliverable_ids": [fields.Command.create({"name": "Inline one", "sequence": 4})]})
        inline = self.day.deliverable_ids.filtered(lambda d: d.name == "Inline one")
        self.assertEqual(inline.company_id, self.company)
        self.assertEqual(self.day.deliverable_count, 4)
        # cascade
        self.day.unlink()
        self.assertFalse(self.Deliverable.search([("id", "in", (self.d1 | self.d2 | self.d_bonus | inline).ids)]))

    # ------------------------------------------------------------------
    # 2 + 5. manager: any field; done stamps done_at / done_by
    # ------------------------------------------------------------------
    def test_manager_edits_anything_and_done_is_stamped(self):
        manager = self.manager_user()
        d1 = self.d1.with_user(manager)
        d1.write({"name": "Copy two sentences", "when": "9 h 15", "detail": "Neatly"})
        self.assertEqual(d1.name, "Copy two sentences")
        d1.write({"done": True})
        self.assertTrue(d1.done)
        self.assertTrue(d1.done_at)
        self.assertEqual(d1.done_by, manager)
        d1.write({"done": False})
        self.assertFalse(d1.done or d1.done_at or d1.done_by)
        # created already done: stamped too
        d = self.Deliverable.with_user(manager).create({"day_id": self.day.id, "name": "Done at creation", "done": True})
        self.assertTrue(d.done_at)
        self.assertEqual(d.done_by, manager)
        self.assertEqual(self.day.deliverable_done_count, 1)

    # ------------------------------------------------------------------
    # 3. portal student ticks only ``done``
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_portal_student_ticks_only_done(self):
        portal = self.portal_user()
        self.student.user_id = portal
        Deliverable = self.Deliverable.with_user(portal)
        self.assertTrue(Deliverable.has_access("read"))
        self.assertTrue(Deliverable.has_access("write"))
        self.assertFalse(Deliverable.has_access("create"))
        self.assertFalse(Deliverable.has_access("unlink"))
        # sees his own three, never the other family's
        self.assertEqual(Deliverable.search([]), (self.d1 | self.d2 | self.d_bonus).with_user(portal))
        with self.assertRaises(AccessError):
            self.d_b.with_user(portal).read(["name"])
        # ticks
        d1 = self.d1.with_user(portal)
        d1.write({"done": True})
        self.assertTrue(d1.done)
        self.assertTrue(d1.done_at)
        self.assertEqual(d1.done_by, portal)
        self.assertEqual(self.day.deliverable_done_count, 1)
        # unticks: cleared
        d1.write({"done": False})
        self.assertFalse(d1.done or d1.done_at or d1.done_by)
        # nothing else, alone or alongside ``done``
        for vals in ({"name": "Renamed"}, {"done": True, "name": "Renamed"}, {"detail": "x"},
                     {"done_at": fields.Datetime.now()}, {"done_by": portal.id}, {"sequence": 9},
                     {"bonus": True}, {"day_id": self.day_b.id}):
            with self.assertRaises(AccessError, msg=str(vals)):
                d1.write(vals)
        self.assertEqual(self.d1.name, "Copy the sentence")
        # another student's deliverable: not even ``done``
        with self.assertRaises(AccessError):
            self.d_b.with_user(portal).write({"done": True})
        self.assertFalse(self.d_b.done)
        # no create, no unlink
        with self.assertRaises(AccessError):
            Deliverable.create({"day_id": self.day.id, "name": "Mine"})
        with self.assertRaises(AccessError):
            d1.unlink()

    # ------------------------------------------------------------------
    # 4. resource user: read only
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_resource_user_reads_only(self):
        teacher = self.resource_user(self.student)
        Deliverable = self.Deliverable.with_user(teacher)
        self.assertEqual(Deliverable.search([]), (self.d1 | self.d2 | self.d_bonus).with_user(teacher))
        self.d1.with_user(teacher).read(["name", "done", "when"])
        with self.assertRaises(AccessError):
            self.d1.with_user(teacher).write({"done": True})
        self.assertFalse(self.d1.done)
        with self.assertRaises(AccessError):
            self.d_b.with_user(teacher).read(["name"])
        # attached to the second student as well: sees both families' lists
        self.student_b.resource_user_ids = [fields.Command.link(teacher.id)]
        self.assertEqual(Deliverable.search([]), (self.d1 | self.d2 | self.d_bonus | self.d_b).with_user(teacher))
