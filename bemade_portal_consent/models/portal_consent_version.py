# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Fields of a version that can no longer change once it is published.
LOCKED_FIELDS = {'document_id', 'number', 'body', 'state', 'published_at', 'published_by_id', 'requires_resign'}


class PortalConsentVersion(models.Model):
    _name = 'portal.consent.version'
    _description = 'Portal Consent Version'
    _order = 'document_id, number desc'

    document_id = fields.Many2one(
        'portal.consent.document', required=True, index=True, ondelete='cascade')
    number = fields.Integer(readonly=True, copy=False, help="Version number, per document (1, 2, 3…).")
    body = fields.Html(translate=True, sanitize=True, string='Text')
    state = fields.Selection(
        [('draft', 'Draft'), ('published', 'Published')],
        default='draft', required=True, readonly=True, copy=False)
    published_at = fields.Datetime(readonly=True, copy=False, string='Published On')
    published_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    requires_resign = fields.Boolean(
        readonly=True, copy=False, string='Requires a New Acceptance',
        help="Users who accepted an earlier version must accept this one.")
    acceptance_ids = fields.One2many('portal.consent.acceptance', 'version_id', string='Acceptances')
    acceptance_count = fields.Integer(compute='_compute_acceptance_count')

    _number_unique = models.Constraint(
        'UNIQUE(document_id, number)', 'A version number is unique within its document.')

    @api.depends('document_id.name', 'number')
    def _compute_display_name(self):
        for version in self:
            version.display_name = _("%(document)s, version %(number)s",
                                     document=version.document_id.name or '', number=version.number)

    def _compute_acceptance_count(self):
        counts = dict(self.env['portal.consent.acceptance']._read_group(
            [('version_id', 'in', self.ids)], ['version_id'], ['__count']))
        for version in self:
            version.acceptance_count = counts.get(version, 0)

    @api.model_create_multi
    def create(self, vals_list):
        next_numbers = {}
        for vals in vals_list:
            vals.update(state='draft', published_at=False, published_by_id=False, requires_resign=False)
            document_id = vals.get('document_id')
            if document_id and not vals.get('number'):
                if document_id not in next_numbers:
                    self.env.cr.execute(
                        "SELECT COALESCE(MAX(number), 0) FROM portal_consent_version WHERE document_id = %s",
                        [document_id])
                    next_numbers[document_id] = self.env.cr.fetchone()[0] + 1
                vals['number'] = next_numbers[document_id]
                next_numbers[document_id] += 1
        return super().create(vals_list)

    def write(self, vals):
        if LOCKED_FIELDS.intersection(vals) and self.filtered(lambda v: v.state == 'published'):
            raise UserError(_("A published consent version is read-only. Write a new version instead."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_published(self):
        if self.filtered(lambda v: v.state == 'published'):
            raise UserError(_("A published consent version cannot be deleted."))

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------
    def _portal_consent_publish(self, requires_resign=True):
        """Publish this draft. The first published version of a document
        always requires a new acceptance."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only a draft version can be published."))
        published = self.document_id.version_ids.filtered(lambda v: v.state == 'published')
        if published and max(published.mapped('number')) > self.number:
            raise UserError(_("A later version of this document is already published."))
        self.write({
            'state': 'published',
            'published_at': fields.Datetime.now(),
            'published_by_id': self.env.user.id,
            'requires_resign': bool(requires_resign) or not published,
        })
        return True

    def action_open_publish_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Publish"),
            'res_model': 'portal.consent.publish.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_version_id': self.id},
        }

    def action_view_acceptances(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'bemade_portal_consent.action_portal_consent_acceptance')
        action['domain'] = [('version_id', '=', self.id)]
        return action

    # ------------------------------------------------------------------
    # Acceptance
    # ------------------------------------------------------------------
    def _portal_consent_accept(self, user, ip=None, user_agent=None):
        """Log ``user``'s acceptance of this published version; returns the
        new ``portal.consent.acceptance`` row."""
        self.ensure_one()
        if self.state != 'published':
            raise UserError(_("Only a published version can be accepted."))
        return self.env['portal.consent.acceptance'].sudo().create({
            'version_id': self.id,
            'user_id': user.id,
            'partner_id': user.partner_id.id,
            'ip': (ip or '')[:64] or False,
            'user_agent': (user_agent or '')[:512] or False,
        })
