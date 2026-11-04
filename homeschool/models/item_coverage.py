# -*- coding: utf-8 -*-
from odoo import api, fields, models

COVERAGE_STATES = [
    ("not_started", "Not started"),
    ("planned", "Planned"),
    ("in_progress", "In progress"),
    ("evidenced", "Evidenced"),
]


class ItemCoverage(models.Model):
    """Coverage of one curriculum item by one family.

    The item is shared by every family; what a family has done about it is not. This row,
    keyed (item, company), holds the family's computed status (from ITS traces and blocks
    only), its manual override, note and date, and the evidence refs written to
    ``coverage.csv``. Rows exist only for the (item, family) pairs that hold evidence or a
    manual status: an item without a row is simply *not started* for that family.
    """
    _name = "homeschool.item.coverage"
    _description = "Curriculum item coverage (per family)"
    _inherit = ["homeschool.company.mixin"]
    _order = "item_id, company_id"

    item_id = fields.Many2one("homeschool.item", required=True, ondelete="cascade", index=True, string="Item")
    item_code = fields.Char(related="item_id.code", string="Code")
    trace_ids = fields.Many2many("homeschool.trace", compute="_compute_evidence_records", string="Traces",
                                 help="The family's traces evidencing this item.")
    block_ids = fields.Many2many("homeschool.block", compute="_compute_evidence_records", string="Blocks",
                                 help="The family's blocks targeting this item.")
    trace_count = fields.Integer(compute="_compute_evidence", store=True)
    block_count = fields.Integer(compute="_compute_evidence", store=True)
    last_evidence_date = fields.Date(compute="_compute_evidence", store=True)
    status_computed = fields.Selection(COVERAGE_STATES, compute="_compute_evidence", store=True, string="Computed status")
    evidence_refs = fields.Char(compute="_compute_evidence", store=True,
                                help="The family's trace codes on this item, as written to coverage.csv.")
    override = fields.Selection(COVERAGE_STATES, string="Manual status", help="Manual status; wins over the computed one when set.")
    status = fields.Selection(COVERAGE_STATES, compute="_compute_status", store=True)
    note = fields.Char()
    date = fields.Date(string="Last manual update", help="Date of the last manual coverage update (from coverage.csv).")

    _item_company_unique = models.Constraint(
        "unique(item_id, company_id)", "One coverage row per item and family."
    )

    @api.depends("item_id.code", "company_id.name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %s" % (rec.item_id.code, rec.company_id.name)

    def _evidence(self):
        """(traces, blocks) of this row's family on this row's item. Read as superuser: the
        row is derived data and must be right whoever triggers its recomputation."""
        self.ensure_one()
        item = self.item_id.sudo()
        company = self.company_id
        return (item.trace_ids.filtered(lambda t: t.company_id == company),
                item.block_ids.filtered(lambda b: b.company_id == company))

    @api.depends("company_id", "item_id.trace_ids", "item_id.trace_ids.company_id", "item_id.block_ids", "item_id.block_ids.company_id")
    def _compute_evidence_records(self):
        for rec in self:
            traces, blocks = rec._evidence()
            rec.trace_ids = traces
            rec.block_ids = blocks

    @api.depends(
        "company_id",
        "item_id.trace_ids", "item_id.trace_ids.date", "item_id.trace_ids.code", "item_id.trace_ids.company_id",
        "item_id.block_ids", "item_id.block_ids.status", "item_id.block_ids.day_id.date", "item_id.block_ids.company_id",
    )
    def _compute_evidence(self):
        # the same rules as the former item-level computation (UC-06 §1), per family
        today = fields.Date.context_today(self)
        for rec in self:
            traces, blocks = rec._evidence()
            rec.trace_count = len(traces)
            rec.block_count = len(blocks)
            rec.evidence_refs = ";".join(traces.sorted("code").mapped("code"))
            dates = traces.mapped("date") + blocks.filtered(lambda b: b.status in ("done", "partial")).mapped("day_id.date")
            rec.last_evidence_date = max(dates) if dates else False
            if traces:
                rec.status_computed = "evidenced"
            elif blocks.filtered(lambda b: b.status in ("done", "partial")):
                rec.status_computed = "in_progress"
            elif blocks.filtered(lambda b: b.status == "planned" and b.day_id.date and b.day_id.date >= today):
                rec.status_computed = "planned"
            elif blocks:
                rec.status_computed = "planned"
            else:
                rec.status_computed = "not_started"

    @api.depends("status_computed", "override")
    def _compute_status(self):
        for rec in self:
            rec.status = rec.override or rec.status_computed or "not_started"

    @api.model
    def _ensure_rows(self, items, company):
        """The rows of ``items`` for ``company``, creating the missing ones. Called when a
        trace or block of ``company`` starts targeting ``items``."""
        if not items or not company:
            return self.browse()
        rows = self.sudo().search([("item_id", "in", items.ids), ("company_id", "=", company.id)])
        missing = items - rows.item_id
        if missing:
            rows |= self.sudo().create([{"item_id": item.id, "company_id": company.id} for item in missing])
        return rows.with_env(self.env)
