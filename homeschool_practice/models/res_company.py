# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    """Practice settings per family. Every value has a sensible default; a family tunes them
    in the back office (Homeschool › Configuration › Practice)."""
    _inherit = "res.company"

    practice_xp_answer = fields.Integer("XP per answer", default=1)
    practice_xp_correct = fields.Integer("Extra XP per correct answer", default=1)
    practice_xp_session = fields.Integer("XP per finished session", default=5)
    practice_xp_secure = fields.Integer("XP when an item becomes automatic", default=10)
    practice_level_base = fields.Integer(
        "Level curve base", default=50,
        help="Level n needs base × (n − 1) × n / 2 XP in total: level 2 at 50, 3 at 150, 4 at 300…")
    practice_timing_margin_ms = fields.Integer(
        "Automaticity margin (ms)", default=1500,
        help="Added to the learner's calibration median to get his threshold.")
    practice_timing_fallback_ms = fields.Integer(
        "Automaticity fallback threshold (ms)", default=3000,
        help="Used until the learner has 10 calibration attempts on the input type.")
    practice_outlier_ms = fields.Integer(
        "Outlier bound (ms)", default=120000,
        help="Attempts slower than this (he walked away) are kept but ignored by mastery.")
