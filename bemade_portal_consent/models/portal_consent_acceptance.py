# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import _, fields, models
from odoo.exceptions import UserError


class PortalConsentAcceptance(models.Model):
    _name = 'portal.consent.acceptance'
    _description = 'Portal Consent Acceptance'
    _order = 'accepted_at desc, id desc'
    _rec_name = 'version_id'

    version_id = fields.Many2one(
        'portal.consent.version', required=True, index=True, ondelete='restrict', readonly=True)
    document_id = fields.Many2one(related='version_id.document_id', store=True, index=True, string='Document')
    user_id = fields.Many2one('res.users', index=True, ondelete='set null', readonly=True)
    partner_id = fields.Many2one('res.partner', index=True, ondelete='set null', readonly=True, string='Contact')
    accepted_at = fields.Datetime(required=True, readonly=True, default=fields.Datetime.now, string='Accepted On')
    ip = fields.Char(readonly=True, string='IP Address')
    user_agent = fields.Char(readonly=True)

    def write(self, vals):
        if vals:
            raise UserError(_("A consent acceptance is never edited."))
        return super().write(vals)
