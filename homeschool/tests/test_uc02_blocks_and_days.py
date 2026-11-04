# -*- coding: utf-8 -*-
"""UC-02 — Blocks are the unit of planning; the day is a container.

Acceptance criteria
-------------------
1. A ``homeschool.day`` has a date, a student, ``start_time`` (default 09:00), opening
   plan, "evening before" checklist, debrief and note (Markdown), and ordered blocks.
2. A ``homeschool.block`` has ``day_id``, ``sequence``, ``kind`` (opening | bloc | pause |
   reading | projects | ressource | debrief | bonus), ``subject_id``, ``name``,
   ``duration_planned`` (minutes), Markdown fields intention / steps / success / fallback,
   ``item_ids``, ``material_ids``, ``project_id``, ``trace_ids``.
3. ``start_time`` is **computed and stored**: the first block starts at the day's start;
   each block starts when the previous one ends; pauses count like any block.
4. A block with ``start_fixed`` set (reading at 14:00) starts there and the computation
   resumes from it; a fixed time earlier than the previous block's end raises a
   ValidationError.
5. Reordering (changing ``sequence``) recomputes every start time of the day.
6. Moving a block to another day (writing ``day_id``) recomputes both days and the
   chatter records the old and new day (tracking on ``day_id`` and ``sequence``).
7. ``end_time`` and the day's ``planned_minutes`` / ``end_time`` are computed sums.
8. Kanban grouped by ``day_id`` and calendar view on ``start_datetime`` /
   ``stop_datetime`` exist (view smoke test).
"""
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase


class TestBlocksAndDays(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.day = self.make_day(date(2026, 1, 12))
        self.opening = self.make_block(self.day, "Opening", 5, 1, kind="opening")
        self.s1 = self.make_block(self.day, "Segment 1", 45, 2, subject_id=self.fle.id)
        self.pause = self.make_block(self.day, "Pause", 15, 3, kind="pause")
        self.s2 = self.make_block(self.day, "Segment 2", 45, 4, subject_id=self.math.id)

    def test_start_times_follow_sequence(self):
        self.assertAlmostEqual(self.day.start_time, 9.0)
        self.assertAlmostEqual(self.opening.start_time, 9.0)
        self.assertAlmostEqual(self.s1.start_time, 9.0 + 5 / 60)
        self.assertAlmostEqual(self.s1.end_time, 9.0 + 50 / 60)
        self.assertAlmostEqual(self.s2.start_time, 9.0 + 65 / 60)
        self.assertEqual(self.s1.start_datetime.strftime("%Y-%m-%d %H:%M"), "2026-01-12 09:05")
        self.assertEqual(self.s2.stop_datetime.strftime("%H:%M"), "10:50")

    def test_pause_is_a_block(self):
        self.assertAlmostEqual(self.pause.start_time, 9.0 + 50 / 60)
        self.assertAlmostEqual(self.s2.start_time, self.pause.end_time)
        # planned minutes of the day exclude pauses
        self.assertEqual(self.day.planned_minutes, 95)

    def test_anchored_block(self):
        reading = self.make_block(self.day, "Reading", 20, 8, kind="reading", anchored=True, start_fixed=14.0)
        self.assertAlmostEqual(reading.start_time, 14.0)
        self.assertAlmostEqual(reading.end_time, 14.0 + 20 / 60)
        after = self.make_block(self.day, "After", 10, 9)
        self.assertAlmostEqual(after.start_time, 14.0 + 20 / 60, msg="computation resumes from the anchor")
        self.assertAlmostEqual(self.day.end_time, 14.5)

    @mute_logger("odoo.sql_db")
    def test_anchor_before_previous_end_refused(self):
        with self.assertRaises(ValidationError):
            self.make_block(self.day, "Too early", 10, 5, anchored=True, start_fixed=9.5)

    def test_reorder_recomputes(self):
        self.s2.sequence = 2
        self.s1.sequence = 4
        self.assertAlmostEqual(self.s2.start_time, 9.0 + 5 / 60)
        self.assertAlmostEqual(self.s1.start_time, 9.0 + 65 / 60)

    def test_move_between_days_tracked_in_chatter(self):
        other = self.make_day(date(2026, 1, 13))
        # creation-time tracking is discarded until precommit runs: flush it first (as MailCommon does)
        self.env.flush_all()
        self.env.cr.precommit.run()
        s2 = self.s2.with_context(tracking_disable=False)
        s2.day_id = other
        self.env.flush_all()
        self.env.cr.precommit.run()
        s2.invalidate_recordset()
        self.assertAlmostEqual(s2.start_time, 9.0, msg="alone on the new day, it starts at the day's start")
        self.assertEqual(self.day.planned_minutes, 50)
        self.assertEqual(other.planned_minutes, 45)
        tracking = s2.message_ids.mapped("tracking_value_ids")
        self.assertTrue(tracking, "the move is tracked")
        self.assertIn("day_id", tracking.mapped("field_id.name"))

    def test_day_totals(self):
        self.assertEqual(self.day.planned_minutes, 95)
        self.assertAlmostEqual(self.day.end_time, 9.0 + 110 / 60)
        self.assertEqual(self.day.block_count, 4)

    def test_views_load(self):
        for view in ("homeschool.view_block_kanban", "homeschool.view_block_calendar", "homeschool.view_block_form"):
            self.assertTrue(self.env.ref(view))
        arch = self.env.ref("homeschool.view_block_kanban").arch
        self.assertIn('default_group_by="day_id"', arch)
        arch = self.env.ref("homeschool.view_block_calendar").arch
        self.assertIn('date_start="start_datetime"', arch)
        with Form(self.s1) as form:
            form.intention = "**Bold** intention"
        self.assertIn("<strong>Bold</strong>", self.s1.intention_html)
