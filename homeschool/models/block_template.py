# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .block import BLOCK_KINDS

WEEKDAYS = [
    ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"), ("3", "Thursday"),
    ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
]


class BlockTemplate(models.Model):
    _name = "homeschool.block.template"
    _description = "Weekday block template (the household grid)"
    _order = "student_id, weekday, sequence, id"

    student_id = fields.Many2one("homeschool.student", ondelete="cascade", help="Empty = default grid for every student.")
    weekday = fields.Selection(WEEKDAYS, required=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(BLOCK_KINDS, required=True, default="bloc")
    subject_id = fields.Many2one("homeschool.subject")
    name = fields.Char(required=True)
    duration_planned = fields.Integer(string="Planned (min)", default=45)
    anchored = fields.Boolean()
    start_fixed = fields.Float()
    alternative = fields.Boolean(help="This block is an alternative to the blocks sharing its alternative group; only the first group member is generated.")
    alternative_group = fields.Char()
    active = fields.Boolean(default=True)

    @api.model
    def _for(self, student, weekday):
        """Templates for a weekday: the student's own if any, else the default grid.
        Alternatives: keep the first template of each alternative group."""
        domain = [("weekday", "=", str(weekday))]
        templates = self.search(domain + [("student_id", "=", student.id)])
        if not templates:
            templates = self.search(domain + [("student_id", "=", False)])
        seen, result = set(), self.browse()
        for t in templates:
            if t.alternative and t.alternative_group:
                if t.alternative_group in seen:
                    continue
                seen.add(t.alternative_group)
            result |= t
        return result

    def _to_block_vals(self):
        self.ensure_one()
        return {
            "sequence": self.sequence,
            "kind": self.kind,
            "subject_id": self.subject_id.id,
            "name": self.name,
            "duration_planned": self.duration_planned,
            "anchored": self.anchored,
            "start_fixed": self.start_fixed,
            "status": "planned",
        }
