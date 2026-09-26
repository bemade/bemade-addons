# -*- coding: utf-8 -*-
from odoo import fields, models


class WeekWizard(models.TransientModel):
    _name = "homeschool.week.wizard"
    _description = "Generate a week's blocks from the templates"

    student_id = fields.Many2one("homeschool.student", required=True, default=lambda self: self.env["homeschool.student"].search([], limit=1))
    date = fields.Date(required=True, default=fields.Date.context_today, help="Any date in the week to generate.")

    def action_generate(self):
        self.ensure_one()
        created, skipped = self.env["homeschool.day"].generate_week(self.student_id, self.date)
        action = self.env["ir.actions.act_window"]._for_xml_id("homeschool.action_block")
        action["domain"] = [("day_id", "in", (created | skipped).ids)]
        action["context"] = {"search_default_group_day": 1}
        return action
