# -*- coding: utf-8 -*-
"""UC-19 — « Fermer la journée »: the day's hour-bearing blocks one screen at a time, then
the day's journal entry.

Acceptance criteria
-------------------
1. ``homeschool.close.day.wizard`` walks exactly the **hour-bearing** blocks of the day
   (``bloc``, ``reading``, ``projects``, ``ressource``, ``bonus``) in ``(sequence, id)``
   order; ``opening`` / ``pause`` / ``debrief`` (``NO_HOURS_KINDS``) never get a screen.
2. Minutes are **never pre-filled**: both minute inputs are blank on a planned block, the
   planned duration is shown beside them. A blank stays a blank (``actuals_recorded`` /
   ``adult_recorded`` false); a typed ``0`` is a value.
3. **Next** writes the current block at once (minutes, status, the three texts) and moves
   on; **Skip this block** writes ``skipped`` and nothing else; **Previous** writes nothing;
   after the last block the wizard shows the day's journal entry; **Finish** creates the
   entry (or writes what changed on the existing one), sets ``done`` on every
   ``NO_HOURS_KINDS`` block still ``planned``, and closes. Abandoning mid-way loses nothing
   already written.
4. A blank adult field leaves the day *Incomplete*; the final screen names those blocks
   (``adult_missing_names``) and still lets the owner finish. With every block given its
   adult minutes and the entry written, ``journal_state`` is ``done`` and the journal API's
   ``status`` reports ``done``.
5. A past day: the three texts and the entry's texts land under ``corrections`` (the
   frozen mixin); minutes and status write in place; an unchanged pre-loaded text never
   produces a correction line.
6. Re-opening the wizard on a half-closed day shows the values already written.
7. Managers only: a plain internal user gets ``AccessError``.
8. Entry points: ``homeschool.day.action_open_close_wizard`` (the day form header) and
   the Track › Close the day menu (today's day of the company's single student).
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tools.misc import mute_logger

from odoo.addons.homeschool.models.block import NO_HOURS_KINDS

from .common import HomeschoolCase


class TestCloseDay(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.Wizard = self.env["homeschool.close.day.wizard"]
        self.Journal = self.env["homeschool.journal"]
        self.today = fields.Date.context_today(self.Day)
        self.today_str = fields.Date.to_string(self.today)
        self.day = self.make_day(self.today)
        self.opening = self.make_block(self.day, "Opening", 10, 1, kind="opening")
        self.b1 = self.make_block(self.day, "P1 Math", 45, 2, subject_id=self.math.id,
                                  intention="measure **time**", success="three readings")
        self.b2 = self.make_block(self.day, "P2 French", 45, 3, subject_id=self.fle.id)
        self.pause = self.make_block(self.day, "Pause", 15, 4, kind="pause")
        self.b3 = self.make_block(self.day, "P3 Science", 30, 5, subject_id=self.st.id)
        self.reading = self.make_block(self.day, "Reading", 20, 6, kind="reading", subject_id=self.fle.id)
        self.debrief = self.make_block(self.day, "Debrief", 10, 7, kind="debrief")

    def _open(self, day=None):
        return self.Wizard.create({"day_id": (day or self.day).id})

    # ------------------------------------------------------------------
    # (a) the screens: hour-bearing blocks only, nothing pre-filled, Next writes
    # ------------------------------------------------------------------
    def test_a_screens_and_next_writes_the_block(self):
        wiz = self._open()
        self.assertEqual(wiz.block_ids, self.b1 | self.b2 | self.b3 | self.reading, "four screens")
        self.assertEqual(wiz.block_ids.ids, [self.b1.id, self.b2.id, self.b3.id, self.reading.id], "sequence order")
        self.assertFalse(set(wiz.block_ids.mapped("kind")) & set(NO_HOURS_KINDS))
        self.assertEqual((wiz.step, wiz.index, wiz.total, wiz.block_id), ("block", 0, 4, self.b1))
        self.assertEqual(wiz.block_duration_planned, 45)
        self.assertIn("<strong>time</strong>", wiz.block_intention_html)
        self.assertIn("three readings", wiz.block_success_html)
        self.assertEqual(wiz.block_status_was, "planned")
        self.assertIn("1 / 4", wiz.title)
        self.assertIn("45", wiz.planned_label)
        with Form(wiz) as form:
            self.assertFalse(form.minutes_total, "never pre-filled")
            self.assertFalse(form.minutes_adult_present, "never pre-filled")
            self.assertEqual(form.status, "done")
            form.minutes_total = "50"
            form.minutes_adult_present = "45"
            form.went_well = "clocks clicked"
            form.went_badly = "a bit long"
            form.note = "stopwatch next time"
        action = wiz.action_next()
        self.assertEqual((action["res_model"], action["res_id"], action["target"]), (wiz._name, wiz.id, "new"))
        self.assertEqual((self.b1.minutes_total, self.b1.minutes_adult_present, self.b1.status), (50, 45, "done"))
        self.assertTrue(self.b1.actuals_recorded and self.b1.adult_recorded)
        self.assertEqual((self.b1.went_well, self.b1.went_badly, self.b1.note), ("clocks clicked", "a bit long", "stopwatch next time"))
        self.assertFalse(self.b1.corrections)
        self.assertEqual((wiz.step, wiz.index, wiz.block_id), ("block", 1, self.b2))
        self.assertFalse(wiz.minutes_total, "the next screen is blank again")
        self.assertFalse(wiz.went_well)
        for block in (self.opening, self.pause, self.debrief):
            self.assertEqual(block.status, "planned")
            self.assertFalse(block.actuals_recorded)

    def test_a_zero_is_a_value_and_text_is_refused(self):
        wiz = self._open()
        with Form(wiz) as form:
            form.minutes_total = "40"
            form.minutes_adult_present = "0"
        wiz.action_next()
        self.assertTrue(self.b1.adult_recorded, "an explicit zero is a recorded value")
        self.assertEqual(self.b1.minutes_adult_present, 0)
        with Form(wiz) as form:
            form.minutes_total = "forty"
        with self.assertRaises(UserError):
            wiz.action_next()
        self.assertFalse(self.b2.actuals_recorded, "nothing written on a refused screen")
        self.assertEqual(wiz.index, 1)
        with Form(wiz) as form:
            form.minutes_total = "30"
            form.minutes_adult_present = "45"
        with self.assertRaises(ValidationError):
            wiz.action_next()

    # ------------------------------------------------------------------
    # (b) skip
    # ------------------------------------------------------------------
    def test_b_skip_writes_skipped_only(self):
        wiz = self._open()
        with Form(wiz) as form:
            form.minutes_total = "50"
            form.went_well = "typed then skipped"
        wiz.action_skip()
        self.assertEqual(self.b1.status, "skipped")
        self.assertFalse(self.b1.actuals_recorded)
        self.assertFalse(self.b1.went_well, "skip writes the status and nothing else")
        self.assertEqual((wiz.index, wiz.block_id), (1, self.b2))

    # ------------------------------------------------------------------
    # (c) blank adult: Incomplete, named, Finish still works
    # ------------------------------------------------------------------
    def _close_all(self, wiz, adult_blank_on=None):
        for block in (self.b1, self.b2, self.b3, self.reading):
            self.assertEqual(wiz.block_id, block)
            with Form(wiz) as form:
                form.minutes_total = str(block.duration_planned)
                if block != adult_blank_on:
                    form.minutes_adult_present = str(block.duration_planned)
            wiz.action_next()
        self.assertEqual(wiz.step, "journal")

    def test_c_blank_adult_leaves_the_day_incomplete(self):
        wiz = self._open()
        self._close_all(wiz, adult_blank_on=self.b3)
        self.assertTrue(self.b3.actuals_recorded and not self.b3.adult_recorded)
        self.assertEqual(wiz.adult_missing_names, "P3 Science")
        self.assertEqual(self.day.journal_state, "incomplete")
        with Form(wiz) as form:
            form.went_well_day = "the morning"
        action = wiz.action_finish()
        self.assertEqual(action["type"], "ir.actions.act_window_close")
        entry = self.day.journal_ids
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry.went_well, "the morning")
        self.assertEqual((self.opening.status, self.pause.status, self.debrief.status), ("done", "done", "done"))
        self.assertFalse(self.opening.actuals_recorded, "closed without a screen, no minutes guessed")
        self.assertEqual(self.day.journal_state, "incomplete", "the blank adult field keeps the day incomplete")
        api = self.env["homeschool.journal.api"].with_user(self.manager_user())
        status = api.status(self.student.id, self.today_str)
        self.assertEqual((status["adult_missing"], status["journal_entry"], status["done"]), (1, True, False))
        self.b3.write({"minutes_adult_present": 30})
        self.assertEqual(self.day.journal_state, "done")

    # ------------------------------------------------------------------
    # (d) complete run → Done, API status done
    # ------------------------------------------------------------------
    def test_d_complete_run_is_done(self):
        wiz = self._open()
        self._close_all(wiz)
        self.assertFalse(wiz.adult_missing_names)
        with Form(wiz) as form:
            form.went_well_day = "all of it"
            form.went_badly_day = "nothing"
            form.notes_day = "- a note"
            form.indicator_notes_day = "R3 0"
        wiz.action_finish()
        entry = self.day.journal_ids
        self.assertEqual((entry.went_well, entry.went_badly, entry.notes, entry.indicator_notes), ("all of it", "nothing", "- a note", "R3 0"))
        self.assertEqual(self.day.journal_state, "done")
        status = self.env["homeschool.journal.api"].with_user(self.manager_user()).status(self.student.id, self.today_str)
        self.assertEqual(status["done"], True)
        self.assertEqual(status["hours_rows"], 4)

    def test_d_finish_refuses_an_empty_new_entry(self):
        wiz = self._open()
        self._close_all(wiz)
        with self.assertRaises(UserError):
            wiz.action_finish()
        self.assertFalse(self.day.journal_ids)
        self.assertEqual(self.opening.status, "planned", "nothing closed by a refused Finish")

    def test_day_without_hour_blocks_starts_on_the_journal(self):
        day = self.make_day(self.today - timedelta(days=3))
        self.make_block(day, "Opening", 10, 1, kind="opening")
        wiz = self._open(day)
        self.assertEqual((wiz.step, wiz.total), ("journal", 0))

    # ------------------------------------------------------------------
    # (e) a past day: texts become corrections, minutes write in place
    # ------------------------------------------------------------------
    def test_e_past_day_corrections(self):
        past = self.make_day(self.today - timedelta(days=1))
        block = self.make_block(past, "Yesterday math", 45, 1, subject_id=self.math.id, went_well="original", note="kept")
        entry = self.Journal.create({"day_id": past.id, "went_well": "day original"})
        wiz = self._open(past)
        self.assertEqual((wiz.went_well, wiz.note), ("original", "kept"), "pre-loaded")
        with Form(wiz) as form:
            form.minutes_total = "40"
            form.minutes_adult_present = "40"
            form.went_well = "rewritten"
            form.went_badly = "late"
        wiz.action_next()
        self.assertEqual((block.minutes_total, block.minutes_adult_present, block.status), (40, 40, "done"))
        self.assertEqual((block.went_well, block.went_badly, block.note), ("original", False, "kept"))
        self.assertEqual(block.corrections,
                         "- **%s** (What worked): rewritten\n- **%s** (What went badly): late" % (self.today_str, self.today_str))
        self.assertEqual(wiz.step, "journal")
        self.assertEqual(wiz.went_well_day, "day original", "pre-loaded")
        with Form(wiz) as form:
            form.went_well_day = "day rewritten"
            form.notes_day = "- added later"
        wiz.action_finish()
        self.assertEqual(entry.went_well, "day original")
        self.assertFalse(entry.notes)
        self.assertEqual(entry.corrections,
                         "- **%s** (What worked): day rewritten\n- **%s** (Notes): - added later" % (self.today_str, self.today_str))

    # ------------------------------------------------------------------
    # (f) abandon after two Next, (g) re-open shows what is there
    # ------------------------------------------------------------------
    def test_f_g_abandon_then_reopen(self):
        wiz = self._open()
        with Form(wiz) as form:
            form.minutes_total = "50"
            form.minutes_adult_present = "45"
            form.went_well = "first"
        wiz.action_next()
        with Form(wiz) as form:
            form.minutes_total = "45"
            form.minutes_adult_present = "0"
            form.status = "partial"
        wiz.action_next()
        # abandoned here (the dialog closed): two blocks closed, the rest untouched
        self.assertEqual((self.b1.status, self.b2.status, self.b3.status, self.reading.status), ("done", "partial", "planned", "planned"))
        self.assertFalse(self.day.journal_ids)
        self.assertEqual(self.day.journal_state, "incomplete")
        # re-open: the written values show, Next without a change rewrites nothing new
        again = self._open()
        self.assertEqual((again.minutes_total, again.minutes_adult_present, again.status, again.went_well), ("50", "45", "done", "first"))
        again.action_next()
        self.assertEqual((again.minutes_total, again.minutes_adult_present, again.status), ("45", "0", "partial"))
        self.assertEqual((self.b1.minutes_total, self.b1.went_well), (50, "first"))
        self.assertFalse(self.b1.corrections)
        again.action_previous()
        self.assertEqual((again.index, again.block_id, again.minutes_total), (0, self.b1, "50"))
        # a past half-closed day re-opened and passed through unchanged: no correction noise
        past = self.make_day(self.today - timedelta(days=2))
        block = self.make_block(past, "Past", 45, 1, subject_id=self.math.id, went_well="as it was",
                                minutes_total=45, minutes_adult_present=45, status="done")
        self.Journal.create({"day_id": past.id, "went_well": "day as it was"})
        past_wiz = self._open(past)
        past_wiz.action_next()
        past_wiz.action_finish()
        self.assertFalse(block.corrections)
        self.assertFalse(past.journal_ids.corrections)

    # ------------------------------------------------------------------
    # (h) access
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_h_manager_only(self):
        plain = self.internal_user()
        with self.assertRaises(AccessError):
            self.Wizard.with_user(plain).create({"day_id": self.day.id})
        with self.assertRaises(AccessError):
            self.day.with_user(plain).action_open_close_wizard()
        manager = self.manager_user()
        action = self.day.with_user(manager).action_open_close_wizard()
        self.assertEqual(action["res_model"], self.Wizard._name)
        wiz = self.Wizard.with_user(manager).browse(action["res_id"])
        self.assertEqual((wiz.day_id, wiz.block_id), (self.day, self.b1))
        with Form(wiz) as form:
            form.minutes_total = "45"
            form.minutes_adult_present = "45"
        wiz.action_next()
        self.assertEqual(self.b1.minutes_total, 45)

    # ------------------------------------------------------------------
    # entry points
    # ------------------------------------------------------------------
    def test_menu_opens_today(self):
        action = self.Wizard.action_open_today()
        wiz = self.Wizard.browse(action["res_id"])
        self.assertEqual(wiz.day_id, self.day)
        self.assertTrue(self.env.ref("homeschool.menu_close_day"))
        self.assertTrue(self.env.ref("homeschool.action_close_day_wizard"))
        self.assertIn('name="action_open_close_wizard"', self.env.ref("homeschool.view_day_form").arch)
        with Form(self.day):
            pass  # the day form, header button included, still loads
