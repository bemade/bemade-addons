# -*- coding: utf-8 -*-
from odoo import api, fields, models


class Student(models.Model):
    _name = "homeschool.student"
    _description = "Home-schooled student"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(related="partner_id.name", store=True, readonly=False)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    birthdate = fields.Date()
    user_id = fields.Many2one("res.users", string="Portal user", help="The student's own portal login, if any.")
    active = fields.Boolean(default=True)
    year_ids = fields.One2many("homeschool.year", "student_id", string="School years")
    day_ids = fields.One2many("homeschool.day", "student_id", string="Days")
    trace_ids = fields.One2many("homeschool.trace", "student_id", string="Traces")


class SchoolYear(models.Model):
    _name = "homeschool.year"
    _description = "School year"
    _order = "date_start desc"

    name = fields.Char(required=True)
    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade")
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    active = fields.Boolean(default=True)
    note = fields.Text()

    _date_order = models.Constraint(
        "check(date_end > date_start)",
        "The school year must end after it starts.",
    )

    def _contains(self, date):
        self.ensure_one()
        return self.date_start <= date <= self.date_end


class Subject(models.Model):
    _name = "homeschool.subject"
    _description = "Subject (matière)"
    _order = "sequence, code"

    code = fields.Char(required=True, help="Short code used in exports (FLE, MATH, ANG, ST, US…).")
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer()
    csv_keys = fields.Char(
        help="Comma-separated keys under which this subject appears in the family CSV files "
        "(e.g. 'francais' for FLE). Used by the importer and the exporter.",
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("unique(code)", "Subject codes must be unique.")

    @api.model
    def _by_csv_key(self, key):
        """Resolve a CSV key or a code to a subject, creating an inactive-free placeholder
        subject when unknown so that imports never silently drop a row."""
        key = (key or "").strip()
        if not key:
            return self.browse()
        for subject in self.search([]):
            keys = {k.strip() for k in (subject.csv_keys or "").split(",") if k.strip()}
            if key == subject.code or key in keys:
                return subject
        return self.create({"code": key.upper()[:16], "name": key, "csv_keys": key})
