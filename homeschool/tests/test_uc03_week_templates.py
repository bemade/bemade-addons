# -*- coding: utf-8 -*-
"""UC-03 — Weekday templates generate a week from the household grid.

Acceptance criteria
-------------------
1. A ``homeschool.block.template`` has weekday, sequence, kind, subject, duration,
   optional ``start_fixed``, default name; templates are per student (and year).
2. A default household grid is shipped as data: Mon/Tue opening 5 + bloc 45 + pause 15 +
   bloc 45 + pause 15 + bloc 35 + debrief 15, reading 20 fixed at 14:00; Wed projects
   9–12 + reading; Thu ressource (an outside teacher 9–11) *or* bloc — the template carries an
   ``alternative`` flag; Fri none.
3. "Generate week" for an ISO week creates days and blocks from the templates;
   running it again does **not** duplicate (days already holding blocks are skipped
   and reported); a holiday (``homeschool.day`` with ``is_off``) gets no blocks.
4. Generated blocks have ``status = planned`` and empty actual minutes.
5. The generated week matches the current ``/journal`` grid used to pre-fill hours
   (Mon/Tue bloc 9–12 · reading 14:00; Wed projects · reading; Thu ressource or bloc ·
   reading; Fri none).
"""
from datetime import date

from .common import HomeschoolCase


class TestWeekTemplates(HomeschoolCase):
    def test_grid_data_present(self):
        Template = self.env["homeschool.block.template"]
        monday = Template._for(self.student, 0)
        self.assertEqual(monday.mapped("kind"), ["opening", "bloc", "pause", "bloc", "pause", "bloc", "debrief", "reading"])
        self.assertEqual(sum(monday.mapped("duration_planned")), 195)
        reading = monday.filtered(lambda t: t.kind == "reading")
        self.assertTrue(reading.anchored)
        self.assertAlmostEqual(reading.start_fixed, 14.0)
        thursday = Template._for(self.student, 3)
        self.assertEqual(thursday.mapped("kind"), ["ressource", "reading"], "only the first alternative is generated")
        self.assertFalse(Template._for(self.student, 4), "Friday: nothing by default")

    def test_generate_week(self):
        created, skipped = self.Day.generate_week(self.student, date(2026, 1, 14))  # a Wednesday
        self.assertEqual(sorted(created.mapped("date")), [date(2026, 1, 12), date(2026, 1, 13), date(2026, 1, 14), date(2026, 1, 15)])
        self.assertFalse(skipped)
        monday = created.filtered(lambda d: d.date == date(2026, 1, 12))
        self.assertEqual(len(monday.block_ids), 8)
        self.assertEqual(set(monday.block_ids.mapped("status")), {"planned"})
        self.assertFalse(any(monday.block_ids.mapped("actuals_recorded")))
        reading = monday.block_ids.filtered(lambda b: b.kind == "reading")
        self.assertAlmostEqual(reading.start_time, 14.0)
        self.assertAlmostEqual(monday.block_ids.sorted("sequence")[-2].end_time, 9.0 + 175 / 60, msg="debrief ends 11:55")
        wednesday = created.filtered(lambda d: d.date == date(2026, 1, 14))
        self.assertEqual(wednesday.block_ids.mapped("kind"), ["opening", "projects", "reading"])

    def test_generate_twice_no_duplicates(self):
        created, _ = self.Day.generate_week(self.student, date(2026, 1, 12))
        n_blocks = self.Block.search_count([("student_id", "=", self.student.id)])
        created2, skipped2 = self.Day.generate_week(self.student, date(2026, 1, 16))  # same ISO week
        self.assertFalse(created2)
        self.assertEqual(skipped2, created)
        self.assertEqual(self.Block.search_count([("student_id", "=", self.student.id)]), n_blocks)

    def test_day_off_skipped(self):
        self.make_day(date(2026, 1, 13), is_off=True, off_reason="holiday")
        created, skipped = self.Day.generate_week(self.student, date(2026, 1, 12))
        self.assertEqual(skipped.mapped("date"), [date(2026, 1, 13)])
        self.assertFalse(skipped.block_ids)
        self.assertEqual(len(created), 3)

    def test_student_specific_templates_win(self):
        Template = self.env["homeschool.block.template"]
        Template.create({"student_id": self.student.id, "weekday": "4", "sequence": 1, "kind": "bloc", "name": "Friday bloc", "duration_planned": 60})
        friday = Template._for(self.student, 4)
        self.assertEqual(friday.mapped("name"), ["Friday bloc"])
        created, _ = self.Day.generate_week(self.student, date(2026, 1, 12))
        self.assertIn(date(2026, 1, 16), created.mapped("date"))
