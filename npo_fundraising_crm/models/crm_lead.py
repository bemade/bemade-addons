# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import fields, models


class CrmLead(models.Model):
    """Relabel the opportunity's sales vocabulary to fundraising terms.

    Only the ``string``/``selection`` labels (the English source) are
    overridden here; all other field behaviour is inherited unchanged. The
    French labels are supplied by ``i18n/fr_CA.po``.
    """

    _inherit = "crm.lead"

    name = fields.Char(string="Donation")
    user_id = fields.Many2one(string="Solicitor")
    team_id = fields.Many2one(string="Development Team")
    expected_revenue = fields.Monetary(string="Expected Amount")
    partner_id = fields.Many2one(string="Donor")
    lost_reason_id = fields.Many2one(string="Decline Reason")
    type = fields.Selection(
        selection=[("lead", "Prospect"), ("opportunity", "Donation")]
    )
    won_status = fields.Selection(
        selection=[("won", "Secured"), ("lost", "Declined"), ("pending", "Pending")]
    )
