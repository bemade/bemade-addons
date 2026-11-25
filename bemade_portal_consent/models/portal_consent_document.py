# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PortalConsentDocument(models.Model):
    _name = 'portal.consent.document'
    _description = 'Portal Consent Document'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Technical identifier, unique. Consumers refer to the document by its XML id or this code.")
    sequence = fields.Integer(default=10, help="Order in which pending documents are shown to a user.")
    description = fields.Text(help="Internal note: what the document is for, who must accept it.")
    active = fields.Boolean(default=True, help="An archived document is never pending.")
    version_ids = fields.One2many('portal.consent.version', 'document_id', string='Versions')
    current_version_id = fields.Many2one(
        'portal.consent.version', compute='_compute_versions',
        help="The latest published version: the text shown to users.")
    required_version_id = fields.Many2one(
        'portal.consent.version', compute='_compute_versions',
        help="The latest published version that requires a new acceptance. A user who accepted it, "
             "or a later published version, is compliant.")
    version_count = fields.Integer(compute='_compute_versions')
    acceptance_count = fields.Integer(compute='_compute_acceptance_count')

    _code_unique = models.Constraint('UNIQUE(code)', 'The code of a consent document must be unique.')

    @api.depends('version_ids.state', 'version_ids.number', 'version_ids.requires_resign')
    def _compute_versions(self):
        for document in self:
            published = document.version_ids.filtered(lambda v: v.state == 'published').sorted('number')
            requiring = published.filtered('requires_resign')
            document.current_version_id = published[-1:]
            # The first published version always requires; fall back to it defensively.
            document.required_version_id = requiring[-1:] or published[:1]
            document.version_count = len(document.version_ids)

    def _compute_acceptance_count(self):
        counts = dict(self.env['portal.consent.acceptance']._read_group(
            [('document_id', 'in', self.ids)], ['document_id'], ['__count']))
        for document in self:
            document.acceptance_count = counts.get(document, 0)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_published(self):
        if self.version_ids.filtered(lambda v: v.state == 'published'):
            raise UserError(_("A document with a published version cannot be deleted. Archive it instead."))

    # ------------------------------------------------------------------
    # Compliance
    # ------------------------------------------------------------------
    def _portal_consent_compliant_users(self, users):
        """The users among ``users`` who comply with this document: they
        accepted its required version or a later published one."""
        self.ensure_one()
        required = self.sudo().required_version_id
        if not required or not users:
            return users.browse()
        rows = self.env['portal.consent.acceptance'].sudo().search_fetch([
            ('document_id', '=', self.id),
            ('user_id', 'in', users.ids),
            ('version_id.state', '=', 'published'),
            ('version_id.number', '>=', required.number),
        ], ['user_id'])
        return users & rows.user_id.with_env(users.env)

    def _portal_consent_pending_users(self):
        """Active portal users whose hook returns this document and who
        have not complied with it. Computed on demand (one hook call per
        portal user)."""
        self.ensure_one()
        if not self.active or not self.sudo().required_version_id:
            return self.env['res.users']
        candidates = self.env['res.users'].sudo().search([('share', '=', True)])
        concerned = candidates.filtered(
            lambda user: not user._is_public() and self in user._portal_consent_documents())
        pending = concerned - self._portal_consent_compliant_users(concerned)
        return self.env['res.users'].browse(pending.ids)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_pending_users(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Pending: %s", self.name),
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('id', 'in', self._portal_consent_pending_users().ids)],
            'context': {'create': False},
        }

    def action_view_acceptances(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'bemade_portal_consent.action_portal_consent_acceptance')
        action['domain'] = [('document_id', '=', self.id)]
        return action
