# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Compliance.

Acceptance criteria
-------------------
* This addon's hook ``res.users._portal_consent_documents()`` returns no
  document: without a consumer, nobody has anything pending.
* A document from the hook is pending only once it has a published version.
* Accepting the required version clears the pending document.
* A later version published without « require a new acceptance » keeps the
  users who accepted an earlier one compliant; accepting the later one also
  counts.
* A later version published with it makes them pending again.
* An archived document is never pending.
* Internal users never have anything pending.
"""
from odoo.tests import TransactionCase, tagged

from ..models.res_users import ResUsers
from .common import ConsentFixtures, consent_hook


@tagged('post_install', '-at_install')
class TestConsentCompliance(ConsentFixtures, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._consent_setup()

    def _pending(self, user):
        return user.sudo()._portal_consent_pending()

    def test_default_hook_is_empty(self):
        # This addon's own implementation (a consumer installed in the same
        # database extends the chain, so call ours directly).
        self.v1._portal_consent_publish(requires_resign=True)
        self.assertFalse(ResUsers._portal_consent_documents(self.portal_a))
        with consent_hook(self.env, lambda user: self.Document):
            self.assertFalse(self._pending(self.portal_a))

    def test_lifecycle(self):
        with consent_hook(self.env, lambda user: self.doc):
            self.assertFalse(self._pending(self.portal_a), 'draft only: nothing pending')
            self.v1._portal_consent_publish(requires_resign=True)
            self.assertEqual(self._pending(self.portal_a), self.doc)
            self.v1._portal_consent_accept(self.portal_a)
            self.assertFalse(self._pending(self.portal_a))
            self.assertEqual(self._pending(self.portal_b), self.doc, 'per user')

            v2 = self._new_version('<p>Wording only.</p>')
            v2._portal_consent_publish(requires_resign=False)
            self.assertFalse(self._pending(self.portal_a), 'no resign: still compliant')
            v2._portal_consent_accept(self.portal_b)
            self.assertFalse(self._pending(self.portal_b), 'a later version counts')

            v3 = self._new_version('<p>New purpose.</p>')
            v3._portal_consent_publish(requires_resign=True)
            self.assertEqual(self._pending(self.portal_a), self.doc, 'resign: pending again')
            self.assertEqual(self._pending(self.portal_b), self.doc)

    def test_archived_document(self):
        self.v1._portal_consent_publish(requires_resign=True)
        with consent_hook(self.env, lambda user: self.doc):
            self.doc.active = False
            self.assertFalse(self._pending(self.portal_a))

    def test_internal_user(self):
        self.v1._portal_consent_publish(requires_resign=True)
        with consent_hook(self.env, lambda user: self.doc):
            self.assertFalse(self._pending(self.staff))
