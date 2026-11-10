# -*- coding: utf-8 -*-
"""Family-defined rewards: earned by goals (never by XP), never expire, spent by parent-recorded
redemptions. The amount of a rule is copied on the ledger line when it is earned, so changing
a rule never rewrites history."""
from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, UserError

from .goal import PERIODS


class RewardType(models.Model):
    _name = "homeschool.reward.type"
    _description = "Reward type"
    _inherit = ["homeschool.company.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True, help="e.g. Gaming time, Credit toward games")
    unit = fields.Char(required=True, translate=True, help="e.g. min, $")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class RewardRule(models.Model):
    _name = "homeschool.reward.rule"
    _description = "What a goal pays"
    _inherit = ["homeschool.company.mixin"]
    _order = "student_id, goal_period, reward_type_id, date_from desc"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    goal_period = fields.Selection(PERIODS, required=True)
    reward_type_id = fields.Many2one("homeschool.reward.type", required=True, ondelete="restrict", check_company=True)
    amount = fields.Float(required=True)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    active = fields.Boolean(default=True)

    _amount_positive = models.Constraint("check(amount > 0)", "A reward amount is positive.")

    @api.model
    def _in_force(self, student, period, day):
        """One rule per reward type: the latest whose ``date_from`` is on or before ``day``."""
        rules = self.sudo().search([("student_id", "=", student.id), ("goal_period", "=", period),
                                    ("date_from", "<=", day)], order="date_from desc, id desc")
        seen, out = set(), self.browse()
        for r in rules:
            if r.reward_type_id.id not in seen:
                seen.add(r.reward_type_id.id)
                out |= r
        return out


class RewardLedger(models.Model):
    _name = "homeschool.reward.ledger"
    _description = "Reward earned or spent"
    _inherit = ["homeschool.company.mixin", "homeschool.practice.append.only"]
    _order = "date desc, id desc"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    reward_type_id = fields.Many2one("homeschool.reward.type", required=True, ondelete="restrict", check_company=True)
    kind = fields.Selection([("earned", "Earned"), ("redeemed", "Used"), ("adjustment", "Adjustment")], required=True)
    amount = fields.Float(required=True, help="Signed: positive when earned, negative when used.")
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    source = fields.Reference([("homeschool.practice.goal.achievement", "Goal reached")])
    note = fields.Char()
    recorded_by = fields.Many2one("res.users", default=lambda self: self.env.user)


class RewardBalance(models.Model):
    _name = "homeschool.reward.balance"
    _description = "Reward balance"
    _auto = False
    _order = "student_id, reward_type_id"

    student_id = fields.Many2one("homeschool.student", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    reward_type_id = fields.Many2one("homeschool.reward.type", readonly=True)
    balance = fields.Float(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                SELECT min(l.id) AS id, l.student_id, l.company_id, l.reward_type_id, sum(l.amount) AS balance
                  FROM homeschool_reward_ledger l
              GROUP BY l.student_id, l.company_id, l.reward_type_id
            )""" % self._table)


class Student(models.Model):
    _inherit = "homeschool.student"

    reward_balance_ids = fields.One2many("homeschool.reward.balance", "student_id", string="Rewards in the bank")
    reward_rule_ids = fields.One2many("homeschool.reward.rule", "student_id", string="Reward rules")

    def _reward_balance(self, reward_type):
        lines = self.env["homeschool.reward.ledger"].sudo().search(
            [("student_id", "=", self.id), ("reward_type_id", "=", reward_type.id)])
        return sum(lines.mapped("amount"))

    def action_reward_redeem(self, reward_type, amount, note=None):
        """A parent records what the learner used. Never below zero."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a parent records a reward used."))
        if amount <= 0:
            raise UserError(self.env._("The amount used must be positive."))
        if amount > self._reward_balance(reward_type) + 1e-9:
            raise UserError(self.env._(
                "%(name)s has %(bal)s %(unit)s in the bank; %(amt)s cannot be used.",
                name=self.name, bal=self._reward_balance(reward_type), unit=reward_type.unit, amt=amount))
        return self.env["homeschool.reward.ledger"].create({
            "student_id": self.id, "reward_type_id": reward_type.id, "kind": "redeemed",
            "amount": -amount, "note": note})

    def _practice_earn(self, achievement):
        """One ``earned`` line per rule in force, once per achievement."""
        Ledger = self.env["homeschool.reward.ledger"].sudo()
        ref = "%s,%s" % (achievement._name, achievement.id)
        if Ledger.search_count([("source", "=", ref)]):
            return Ledger
        rules = self.env["homeschool.reward.rule"]._in_force(self, achievement.period, achievement.period_start)
        return Ledger.create([{
            "student_id": self.id, "reward_type_id": r.reward_type_id.id, "kind": "earned",
            "amount": r.amount, "source": ref, "recorded_by": self.env.ref("base.user_root").id,
        } for r in rules])

    def _practice_balances(self):
        types = self.env["homeschool.reward.type"].sudo().search([("company_id", "=", self.company_id.id)])
        return [{"type_id": t.id, "name": t.name, "unit": t.unit, "balance": self._reward_balance(t)} for t in types]


class PracticeSession(models.Model):
    _inherit = "homeschool.practice.session"

    def _on_goals_reached(self, events, achievements):
        res = super()._on_goals_reached(events, achievements)
        for ach in achievements:
            for line in self.student_id._practice_earn(ach):
                events.setdefault("rewards", []).append(
                    {"name": line.reward_type_id.name, "unit": line.reward_type_id.unit, "amount": line.amount})
        return res
