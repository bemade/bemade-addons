# -*- coding: utf-8 -*-
"""UC-17 — Per-block journal: what worked / what went badly on the block itself.

Acceptance criteria
-------------------
1. ``homeschool.block`` carries ``went_well`` and ``went_badly`` (Markdown, rendered
   twins) and ``corrections`` next to its ``note``.
2. The same past-day freeze as the journal: a write of ``went_well`` / ``went_badly`` /
   ``note`` on a block of a **past** day lands as a dated line under ``corrections``
   (``- **<today>** (<label>): <text>``) and the field itself is unchanged; today's block
   takes the text in place.
3. Minutes and ``status`` of a past block stay freely editable (closing yesterday late
   is normal) — only the three texts are frozen.
4. ``journal_force_edit`` in the context bypasses the freeze (imports, repairs).
5. ``append_note(field_name, text)`` grows the field today and corrects a past block.
6. The journal's own freeze is untouched (UC-08 stays green — shared helper).
7. The block form exposes the three texts on its « Block journal » page.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import Form

from .common import HomeschoolCase


class TestBlockJournal(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.context_today(self.Day)
        self.today_str = fields.Date.to_string(self.today)
        self.day = self.make_day(self.today)
        self.block = self.make_block(self.day, "Segment 1", 45, 1, subject_id=self.fle.id)
        self.past_day = self.make_day(self.today - timedelta(days=1))
        self.past = self.make_block(self.past_day, "Yesterday's segment", 45, 1, subject_id=self.math.id,
                                    went_well="original", went_badly="bad", note="kept")

    def test_today_block_takes_the_texts_in_place(self):
        self.block.write({"went_well": "went fine", "went_badly": "too long", "note": "a remark"})
        self.assertEqual((self.block.went_well, self.block.went_badly, self.block.note), ("went fine", "too long", "a remark"))
        self.assertFalse(self.block.corrections)
        self.assertIn("<p>went fine</p>", self.block.went_well_html)
        self.assertIn("<p>too long</p>", self.block.went_badly_html)

    def test_past_block_texts_are_corrected_not_rewritten(self):
        self.past.write({"went_well": "rewritten", "note": "late note"})
        self.assertEqual((self.past.went_well, self.past.went_badly, self.past.note), ("original", "bad", "kept"),
                         "a past block's texts are never edited in place")
        self.assertEqual(self.past.corrections,
                         "- **%s** (What worked): rewritten\n- **%s** (Note): late note" % (self.today_str, self.today_str))
        self.past.write({"went_badly": "also"})
        self.assertEqual(self.past.went_badly, "bad")
        self.assertTrue(self.past.corrections.endswith("- **%s** (What went badly): also" % self.today_str))
        self.assertIn("rewritten", self.past.corrections_html)

    def test_past_block_minutes_and_status_write_in_place(self):
        self.past.write({"minutes_total": 50, "minutes_adult_present": 40, "status": "done"})
        self.assertEqual((self.past.minutes_total, self.past.minutes_adult_present, self.past.status), (50, 40, "done"))
        self.assertTrue(self.past.actuals_recorded and self.past.adult_recorded)
        self.assertFalse(self.past.corrections, "closing yesterday late is not a correction")
        # a mixed write: the minutes land, the text is corrected
        self.past.write({"minutes_total": 55, "went_well": "after all"})
        self.assertEqual(self.past.minutes_total, 55)
        self.assertEqual(self.past.went_well, "original")
        self.assertIn("(What worked): after all", self.past.corrections)

    def test_force_edit_bypasses_the_freeze(self):
        self.past.with_context(journal_force_edit=True).write({"went_well": "repaired", "note": "fixed"})
        self.assertEqual((self.past.went_well, self.past.note), ("repaired", "fixed"))
        self.assertFalse(self.past.corrections)

    def test_append_note(self):
        self.block.append_note("went_well", "first")
        self.block.append_note("went_well", "second")
        self.assertEqual(self.block.went_well, "first\nsecond")
        self.assertFalse(self.block.corrections)
        self.past.append_note("went_badly", "late")
        self.assertEqual(self.past.went_badly, "bad")
        self.assertEqual(self.past.corrections, "- **%s** (What went badly): late" % self.today_str)

    def test_journal_freeze_untouched(self):
        entry = self.env["homeschool.journal"].create({"day_id": self.past_day.id, "went_well": "original"})
        entry.write({"went_well": "rewritten", "indicator_notes": "R3 1"})
        self.assertEqual(entry.went_well, "original")
        self.assertEqual(entry.corrections,
                         "- **%s** (What worked): rewritten\n- **%s** (Indicator Notes): R3 1" % (self.today_str, self.today_str))

    def test_block_form_journal_page(self):
        with Form(self.block) as form:
            form.went_well = "from the form"
            form.went_badly = "a bit long"
            form.note = "note from the form"
        self.assertEqual((self.block.went_well, self.block.went_badly, self.block.note),
                         ("from the form", "a bit long", "note from the form"))
        with Form(self.past) as form:
            form.went_well = "late from the form"
        self.assertEqual(self.past.went_well, "original")
        self.assertIn("(What worked): late from the form", self.past.corrections)
