# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import fields, models


class CrmTeam(models.Model):
    """A "Sales Team" is a fundraising "Development Team"."""

    _inherit = "crm.team"

    name = fields.Char(string="Development Team")
