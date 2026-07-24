from odoo import fields, models


class CbetDomain(models.Model):
    """UC-CAT-01 — competency domains (UNI, PRE, TST, …)."""

    _name = "cbet.domain"
    _description = "CBET Competency Domain"
    _order = "sequence, code"

    code = fields.Char(required=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    competency_ids = fields.One2many("cbet.competency", "domain_id", string="Competencies")
    competency_count = fields.Integer(compute="_compute_competency_count")

    _code_uniq = models.Constraint(
        "unique(code)",
        "A competency domain with this code already exists.",
    )

    def _compute_competency_count(self):
        data = self.env["cbet.competency"]._read_group(
            [("domain_id", "in", self.ids)], ["domain_id"], ["__count"],
        )
        counts = {domain.id: count for domain, count in data}
        for domain in self:
            domain.competency_count = counts.get(domain.id, 0)
