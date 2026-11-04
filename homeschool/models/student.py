# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class Student(models.Model):
    _name = "homeschool.student"
    _description = "Home-schooled student"
    _inherit = ["mail.thread", "homeschool.company.mixin"]
    _order = "name"

    name = fields.Char(related="partner_id.name", store=True, readonly=False)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    birthdate = fields.Date()
    user_id = fields.Many2one("res.users", string="Portal user", help="The student's own portal login, if any.")
    resource_user_ids = fields.Many2many(
        "res.users", "homeschool_student_resource_user_rel", "student_id", "user_id",
        string="Resource users", domain="[('share', '=', True)]",
        help="Portal users (outside teachers) who see this student's days, blocks, institutional traces and material.",
    )
    active = fields.Boolean(default=True)
    year_ids = fields.One2many("homeschool.year", "student_id", string="School years")
    day_ids = fields.One2many("homeschool.day", "student_id", string="Days")
    trace_ids = fields.One2many("homeschool.trace", "student_id", string="Traces")

    @api.constrains("resource_user_ids")
    def _check_resource_users_share(self):
        for rec in self:
            internal = rec.resource_user_ids.filtered(lambda u: not u.share)
            if internal:
                raise ValidationError(self.env._(
                    "Resource users must be portal users; %(names)s are internal users. "
                    "Give an internal user the Homeschool manager group and a company instead.",
                    names=", ".join(internal.mapped("name")),
                ))


class SchoolYear(models.Model):
    _name = "homeschool.year"
    _description = "School year"
    _inherit = ["homeschool.company.mixin"]
    _order = "date_start desc"

    name = fields.Char(required=True)
    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", check_company=True)
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
    def _by_csv_key(self, key, create=True):
        """Resolve a CSV key or a code to one subject.

        The exact ``code`` wins; then the ``csv_keys``, subjects taken in id order so the
        seeded ones win over later additions (a subject whose keys happen to list another
        subject's code never shadows it). A key holding a separator (``,`` or ``;``) is a
        list, never one subject: empty recordset. When nothing matches, ``create=True`` (the
        curriculum imports: ``matiere`` / ``domaine`` columns) creates a placeholder subject so
        that no item is dropped; ``create=False`` (hours, traces) returns an empty recordset
        and the caller reports the key."""
        key = (key or "").strip()
        if not key or "," in key or ";" in key:
            return self.browse()
        subjects = self.search([], order="id")
        exact = subjects.filtered(lambda s: s.code == key)
        if exact:
            return exact[:1]
        for subject in subjects:
            keys = {k.strip() for k in (subject.csv_keys or "").split(",") if k.strip()}
            if key in keys:
                return subject
        if not create:
            return self.browse()
        return self.create({"code": key.upper()[:16], "name": key, "csv_keys": key})
