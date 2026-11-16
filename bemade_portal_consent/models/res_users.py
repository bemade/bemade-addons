# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _portal_consent_documents(self):
        """Hook: the ``portal.consent.document`` records this user must
        accept. Consumers extend it with ``super()``. Called on one user,
        as superuser by the gate. Default: none."""
        self.ensure_one()
        return self.env['portal.consent.document']

    def _portal_consent_pending(self):
        """The documents of the hook this user has not complied with,
        ordered by sequence. Archived documents and documents without a
        published version are never pending; internal and public users
        never have anything pending."""
        self.ensure_one()
        empty = self.env['portal.consent.document']
        if not self.share or self._is_public():
            return empty
        documents = self._portal_consent_documents().sudo().filtered(
            lambda d: d.active and d.required_version_id)
        pending = documents.filtered(lambda d: not d._portal_consent_compliant_users(self.sudo()))
        return empty.browse(pending.sorted(lambda d: (d.sequence, d.id)).ids)
