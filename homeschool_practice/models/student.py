# -*- coding: utf-8 -*-
from odoo import fields, models

WEEKDAYS = "1234567"


class Student(models.Model):
    _inherit = "homeschool.student"

    practice_handedness = fields.Selection(
        [("right", "Right-handed"), ("left", "Left-handed")], default="right", required=True,
        help="The lesson screen puts the keypad and the choices on this side.")
    practice_weekdays = fields.Char(
        default="12345", help="Practice days (ISO weekdays, 1 = Monday): quests are drawn on these days only.")
    practice_quests_per_day = fields.Integer(default=3)
    practice_unit_access_ids = fields.One2many("homeschool.practice.unit.access", "student_id", string="Units")

    def _practice_is_practice_day(self, day):
        return str(day.isoweekday()) in (self.sudo().practice_weekdays or "")

    def _practice_needs(self, day):
        """Unlocked units with what they need today, most first: ``[(unit, count, due_seen)]`` —
        ``count`` = new or due items, ``due_seen`` = items already seen and due again (review)."""
        self.ensure_one()
        units = self.env["homeschool.practice.unit.access"].sudo().search(
            [("student_id", "=", self.id), ("state", "=", "unlocked")]).unit_id
        rows = self.env["homeschool.practice.mastery"].sudo().search(
            [("student_id", "=", self.id), ("unit_id", "in", units.ids)])
        out = []
        for unit in units:
            mine = rows.filtered(lambda r: r.unit_id == unit)
            out.append((unit, len(mine.filtered(lambda r: not r.last_seen or r.due_on <= day)),
                        len(mine.filtered(lambda r: r.last_seen and r.due_on <= day))))
        return sorted(out, key=lambda x: (-x[1], x[0].deck_id.sequence, x[0].sequence, x[0].id))
