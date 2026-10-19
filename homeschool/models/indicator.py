# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

from .day import iso_week_label


class Indicator(models.Model):
    _name = "homeschool.indicator"
    _description = "Indicator definition"
    _inherit = ["homeschool.company.mixin"]
    _order = "csv_sequence, code"

    code = fields.Char(required=True, index=True)
    csv_sequence = fields.Integer(default=100000, help="Row order in the family CSV.")
    porte = fields.Char(string="Bears on", help="Which need / objective the indicator bears on (e.g. 'R1 / D5').")
    name = fields.Char(required=True)
    unit = fields.Char()
    period = fields.Selection([("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"), ("periodic", "Periodic")], required=True, default="weekly")
    cadence_raw = fields.Char(help="The 'cadence' value of the family CSV, verbatim.")
    direction = fields.Selection([("up", "Higher is better"), ("down", "Lower is better"), ("stable", "Stable")])
    sens_raw = fields.Char(help="The 'sens' value of the family CSV, verbatim.")
    threshold = fields.Char()
    source = fields.Char()
    note = fields.Text()
    computed = fields.Boolean(help="Computed from records (e.g. adult-present hours per week); values are recorded on demand.")
    value_ids = fields.One2many("homeschool.indicator.value", "indicator_id", string="Values")
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("unique(company_id, code)", "Indicator codes must be unique within a family.")

    @api.model
    def _by_code(self, code, company=None):
        """The indicator with that code in ``company`` (default: the current company)."""
        company = company or self.env.company
        return self.with_context(active_test=False).search([("code", "=", code), ("company_id", "=", company.id)], limit=1)

    @api.model
    def adult_hours_for_week(self, student, any_date):
        """Adult-present hours for the ISO week containing ``any_date`` (R1-ADULTE)."""
        label = iso_week_label(any_date)
        groups = self.env["homeschool.block"]._read_group(
            [("student_id", "=", student.id), ("day_id.iso_week", "=", label)],
            [], ["minutes_adult_present:sum"],
        )
        minutes = groups[0][0] if groups else 0
        return round((minutes or 0) / 60.0, 2)

    @api.model
    def record_adult_hours(self, student, any_date, note=None):
        """Write (or update) the R1-ADULTE value of ``student`` for the ISO week containing
        ``any_date`` from the blocks' adult-present minutes; the indicator is created in the
        student's family when it does not exist yet. Returns the value record. Shared by the
        review's button and « Fermer la semaine »."""
        company = student.company_id
        Value = self.env["homeschool.indicator.value"]
        indicator = self._by_code("R1-ADULTE", company)
        if not indicator:
            indicator = self.create({"code": "R1-ADULTE", "name": "Adult-present hours (week)", "unit": "h/week",
                                     "period": "weekly", "direction": "down", "computed": True,
                                     "company_id": company.id})
        hours = self.adult_hours_for_week(student, any_date)
        existing = Value.search([("indicator_id", "=", indicator.id), ("student_id", "=", student.id),
                                 ("iso_week", "=", iso_week_label(any_date))], limit=1)
        vals = {"value": hours}
        if note:
            vals["note"] = note
        if existing:
            existing.write(vals)
            return existing
        monday = any_date - timedelta(days=any_date.weekday())
        return Value.create(dict(vals, indicator_id=indicator.id, student_id=student.id, date=monday, company_id=company.id))

    def missing_for_week(self, any_date, company=None):
        """Weekly indicators (non computed) of ``company`` (default: the current company)
        with no value dated inside the ISO week."""
        company = company or self.env.company
        label = iso_week_label(any_date)
        weekly = self.search([("period", "=", "weekly"), ("computed", "=", False), ("company_id", "=", company.id)])
        recorded = self.env["homeschool.indicator.value"].search(
            [("indicator_id", "in", weekly.ids), ("iso_week", "=", label)]
        ).mapped("indicator_id")
        return weekly - recorded


class IndicatorValue(models.Model):
    _name = "homeschool.indicator.value"
    _description = "Indicator value"
    _inherit = ["homeschool.company.mixin"]
    _order = "date desc, indicator_id"

    indicator_id = fields.Many2one("homeschool.indicator", required=True, ondelete="cascade", index=True, check_company=True)
    code = fields.Char(related="indicator_id.code", store=True)
    student_id = fields.Many2one("homeschool.student", ondelete="cascade", check_company=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    iso_week = fields.Char(compute="_compute_iso_week", store=True, index=True)
    value = fields.Float(required=True, help="A skipped indicator has no row at all — never write a zero that was not said.")
    note = fields.Char()

    _indicator_date_unique = models.Constraint(
        "unique(indicator_id, student_id, date)", "This indicator already has a value on that date."
    )

    @api.depends("date")
    def _compute_iso_week(self):
        for rec in self:
            rec.iso_week = iso_week_label(rec.date) if rec.date else False
