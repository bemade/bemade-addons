# -*- coding: utf-8 -*-
"""« Fermer la journée » (UC-19): the day's hour-bearing blocks one screen at a time, then
the day's journal entry.

A multi-step transient: every **Next** writes the current block at once and the wizard
re-opens itself on the same record (``_reopen``); abandoning mid-way loses nothing that was
already written. Minutes are never pre-filled — the two inputs are text so that a blank is
a blank (an Integer field reads ``0`` when empty and the web client would show « 0 » on
every screen); a typed ``0`` is a value.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.block import NO_HOURS_KINDS

CLOSE_STATUS = [("done", "Done"), ("partial", "Partial"), ("skipped", "Skipped")]


class CloseDayWizard(models.TransientModel):
    _name = "homeschool.close.day.wizard"
    _description = "Close the day"

    day_id = fields.Many2one("homeschool.day", required=True, ondelete="cascade", string="Day")
    step = fields.Selection([("block", "Block"), ("journal", "Journal")], default="block", required=True)
    index = fields.Integer(default=0, help="0-based position of the current block among the day's hour-bearing blocks.")
    block_ids = fields.Many2many("homeschool.block", compute="_compute_blocks", string="Blocks to close")
    total = fields.Integer(compute="_compute_blocks", string="Number of blocks to close")
    block_id = fields.Many2one("homeschool.block", compute="_compute_block", string="Current block")
    title = fields.Char(compute="_compute_block")
    planned_label = fields.Char(compute="_compute_block")
    block_name = fields.Char(related="block_id.name")
    block_kind = fields.Selection(related="block_id.kind")
    block_subject_id = fields.Many2one(related="block_id.subject_id")
    block_duration_planned = fields.Integer(related="block_id.duration_planned")
    block_intention_html = fields.Html(related="block_id.intention_html", sanitize=False)
    block_success_html = fields.Html(related="block_id.success_html", sanitize=False)
    block_status_was = fields.Selection(related="block_id.status", string="Status before")

    # the block screen — pre-loaded from the block when it already holds values
    minutes_total = fields.Char(string="Actual (min)", help="Whole minutes. Leave blank when not measured: a blank is honest, a zero is a value.")
    minutes_adult_present = fields.Char(string="Adult present (min)", help="Whole minutes with an adult present. Leave blank when not measured.")
    status = fields.Selection(CLOSE_STATUS, default="done", required=True)
    went_well = fields.Text(string="What worked", help="Markdown. As it was — a clean journal is a false journal.")
    went_badly = fields.Text(string="What went badly", help="Markdown.")
    note = fields.Text(help="Markdown.")

    # the journal screen — pre-loaded from the day's entry
    went_well_day = fields.Text(string="What worked (day)", help="Markdown.")
    went_badly_day = fields.Text(string="What went badly (day)", help="Markdown.")
    notes_day = fields.Text(string="Notes (day)", help="Markdown.")
    indicator_notes_day = fields.Text(string="Indicator notes (day)", help="Free text: conflicts, withdrawal, spontaneous engagement, recovery delay — tallied at the weekly review.")
    adult_missing_names = fields.Char(compute="_compute_adult_missing_names", string="Blocks without adult minutes")

    # ------------------------------------------------------------------
    # computes
    # ------------------------------------------------------------------
    def _hour_blocks(self):
        self.ensure_one()
        return self.day_id.block_ids.filtered(lambda b: b.kind not in NO_HOURS_KINDS).sorted(lambda b: (b.sequence, b.id))

    @api.depends("day_id.block_ids.kind", "day_id.block_ids.sequence")
    def _compute_blocks(self):
        for wiz in self:
            blocks = wiz._hour_blocks()
            wiz.block_ids = blocks
            wiz.total = len(blocks)

    @api.depends("day_id", "index", "block_ids")
    def _compute_block(self):
        for wiz in self:
            blocks = wiz._hour_blocks()
            block = blocks[wiz.index] if 0 <= wiz.index < len(blocks) else blocks.browse()
            wiz.block_id = block
            wiz.title = self.env._("Block %(n)s / %(total)s — %(name)s", n=wiz.index + 1, total=len(blocks), name=block.name or "") if block else ""
            wiz.planned_label = self.env._("planned: %(minutes)s min", minutes=block.duration_planned) if block else ""

    @api.depends("day_id.block_ids.adult_recorded", "day_id.block_ids.actuals_recorded", "day_id.block_ids.status", "step")
    def _compute_adult_missing_names(self):
        for wiz in self:
            pending = wiz.day_id._pending_blocks() if wiz.day_id else wiz.day_id.block_ids
            wiz.adult_missing_names = ", ".join(pending.mapped("name"))

    # ------------------------------------------------------------------
    # navigation
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wiz in wizards:
            wiz._goto(wiz.index)
        return wizards

    def _goto(self, index):
        """Move to the block at ``index`` (its stored values pre-loaded) or, past the last
        one, to the journal screen (the entry pre-loaded)."""
        self.ensure_one()
        blocks = self._hour_blocks()
        index = max(index, 0)
        if index >= len(blocks):
            entry = self.day_id.journal_ids[:1]
            self.write({
                "index": len(blocks), "step": "journal",
                "went_well_day": entry.went_well or False, "went_badly_day": entry.went_badly or False,
                "notes_day": entry.notes or False, "indicator_notes_day": entry.indicator_notes or False,
            })
            return
        block = blocks[index]
        self.write({
            "index": index, "step": "block",
            "minutes_total": str(block.minutes_total) if block.actuals_recorded else False,
            "minutes_adult_present": str(block.minutes_adult_present) if block.adult_recorded else False,
            "status": block.status if block.status in dict(CLOSE_STATUS) else "done",
            "went_well": block.went_well or False, "went_badly": block.went_badly or False, "note": block.note or False,
        })

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Close the day — %s", self.day_id.display_name),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }

    @api.model
    def action_open_today(self):
        """Track › Close the day: today's day of the company's single student."""
        students = self.env["homeschool.student"].search([("company_id", "=", self.env.company.id)], limit=2)
        if len(students) != 1:
            raise UserError(self.env._("This company has %(count)s students: open the day and close it from its form.", count=len(students)))
        day = self.env["homeschool.day"]._get_or_create(students, fields.Date.context_today(self))
        return self.create({"day_id": day.id})._reopen()

    # ------------------------------------------------------------------
    # buttons
    # ------------------------------------------------------------------
    @api.model
    def _minutes(self, value):
        """``""`` / ``False`` → ``False`` (a blank: nothing recorded); digits → the integer."""
        text = (value or "").strip()
        if not text:
            return False
        try:
            return int(text)
        except ValueError:
            raise UserError(self.env._("Minutes must be a whole number: %(value)s", value=text))

    def _changed_texts(self, record, pairs):
        """``{target_field: new_text}`` for the wizard fields whose text differs from the
        record's — an unchanged pre-loaded text is never rewritten (a past day would get a
        correction line for nothing)."""
        vals = {}
        for wizard_field, target_field in pairs:
            new = self[wizard_field] or False
            if new != (record[target_field] or False):
                vals[target_field] = new
        return vals

    def action_next(self):
        """Write the current block (minutes only when given, status, the texts that
        changed) and move to the next screen."""
        self.ensure_one()
        block = self.block_id
        if block:
            vals = {
                "status": self.status,
                "minutes_total": self._minutes(self.minutes_total),
                "minutes_adult_present": self._minutes(self.minutes_adult_present),
            }
            vals.update(self._changed_texts(block, (("went_well", "went_well"), ("went_badly", "went_badly"), ("note", "note"))))
            block.write(vals)
        self._goto(self.index + 1)
        return self._reopen()

    def action_skip(self):
        """``skipped``, nothing else; next screen."""
        self.ensure_one()
        if self.block_id:
            self.block_id.write({"status": "skipped"})
        self._goto(self.index + 1)
        return self._reopen()

    def action_previous(self):
        """Back one screen; nothing is written."""
        self.ensure_one()
        self._goto(self.index - 1)
        return self._reopen()

    def action_finish(self):
        """The day's entry — created, or the changed fields written (a past day's land
        under its corrections) — then every no-hours block still planned is set done."""
        self.ensure_one()
        day = self.day_id
        pairs = (("went_well_day", "went_well"), ("went_badly_day", "went_badly"),
                 ("notes_day", "notes"), ("indicator_notes_day", "indicator_notes"))
        entry = day.journal_ids[:1]
        if entry:
            vals = self._changed_texts(entry, pairs)
            if vals:
                entry.write(vals)
        else:
            vals = {target: self[source] or False for source, target in pairs}
            if not any(vals.values()):
                raise UserError(self.env._("Write at least one line in the journal before finishing."))
            self.env["homeschool.journal"].create(dict(vals, day_id=day.id))
        day.block_ids.filtered(lambda b: b.kind in NO_HOURS_KINDS and b.status == "planned").write({"status": "done"})
        return {"type": "ir.actions.act_window_close"}
