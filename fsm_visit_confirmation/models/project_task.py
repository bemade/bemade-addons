from odoo import models, fields, api


class Task(models.Model):
    _inherit = "project.task"

    def action_approve_booking(self):
        self.ensure_one()
        self.state = "03_approved"
