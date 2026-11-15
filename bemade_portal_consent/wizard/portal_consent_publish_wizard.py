# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import api, fields, models


class PortalConsentPublishWizard(models.TransientModel):
    _name = 'portal.consent.publish.wizard'
    _description = 'Publish a Portal Consent Version'

    version_id = fields.Many2one('portal.consent.version', required=True, ondelete='cascade')
    document_id = fields.Many2one(related='version_id.document_id')
    is_first = fields.Boolean(compute='_compute_is_first', string='First Published Version')
    requires_resign = fields.Boolean(
        string='Require a New Acceptance', default=True,
        help="Users who accepted an earlier version must accept this one before using the portal again. "
             "Leave it unchecked for a correction that changes nothing for them (typo, layout).")

    @api.depends('version_id')
    def _compute_is_first(self):
        for wizard in self:
            wizard.is_first = not wizard.version_id.document_id.version_ids.filtered(
                lambda v: v.state == 'published')

    def action_confirm(self):
        self.ensure_one()
        self.version_id._portal_consent_publish(requires_resign=self.requires_resign or self.is_first)
        return {'type': 'ir.actions.act_window_close'}
