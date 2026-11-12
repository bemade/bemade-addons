# -*- coding: utf-8 -*-
from odoo import api, fields, models


class UnlockWizard(models.TransientModel):
    _name = "homeschool.practice.unlock.wizard"
    _description = "Unlock practice units"

    student_id = fields.Many2one("homeschool.student", required=True)
    unit_ids = fields.Many2many("homeschool.practice.unit", string="Units taught")

    def action_unlock(self):
        self.unit_ids.action_unlock(self.student_id)
        return {"type": "ir.actions.act_window_close"}


class RedeemWizard(models.TransientModel):
    _name = "homeschool.reward.redeem.wizard"
    _description = "Record a reward used"

    student_id = fields.Many2one("homeschool.student", required=True)
    reward_type_id = fields.Many2one("homeschool.reward.type", required=True)
    balance = fields.Float(compute="_compute_balance")
    amount = fields.Float(required=True)
    note = fields.Char()

    @api.depends("student_id", "reward_type_id")
    def _compute_balance(self):
        for w in self:
            w.balance = w.student_id._reward_balance(w.reward_type_id) if w.student_id and w.reward_type_id else 0

    def action_redeem(self):
        self.student_id.action_reward_redeem(self.reward_type_id, self.amount, self.note)
        return {"type": "ir.actions.act_window_close"}


class UnitAccess(models.Model):
    _inherit = "homeschool.practice.unit.access"

    def action_unlock_row(self):
        for row in self:
            row.unit_id.action_unlock(row.student_id)

    def action_lock_row(self):
        for row in self:
            row.unit_id.action_lock(row.student_id)
