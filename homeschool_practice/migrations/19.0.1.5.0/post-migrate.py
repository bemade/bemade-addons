# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""19.0.1.5.0: a quest every day for the times-tables decks and the « Grammaire » deck.

The decks already exist on upgraded databases (the loader only flags « Grammaire » when it
creates it), so flag them here: the times-tables decks by their item keys (« 7x8 »), the
grammar starter deck by name.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["homeschool.practice.deck"]._flag_daily_decks()
