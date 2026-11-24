# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Acceptance log.

Acceptance criteria
-------------------
* An acceptance records the version, the document, the user, the partner,
  the time, the IP address and the user agent.
* Only a published version can be accepted.
* An acceptance is never edited, not even by an administrator.
* Only an administrator deletes an acceptance; a consent manager reads all
  of them but deletes none.
* A portal user reads their own acceptances and never another user's; a
  portal user cannot create one directly.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from .common import ConsentFixtures


@tagged('post_install', '-at_install')
class TestConsentAcceptanceLog(ConsentFixtures, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._consent_setup()
        cls.manager = new_test_user(
            cls.env, login='tc5390_manager',
            groups='base.group_user,bemade_portal_consent.group_portal_consent_manager')
        cls.v1._portal_consent_publish(requires_resign=True)
        cls.row_a = cls.v1._portal_consent_accept(cls.portal_a, ip='192.0.2.10', user_agent='SampleBrowser/1.0')
        cls.row_b = cls.v1._portal_consent_accept(cls.portal_b, ip='192.0.2.11', user_agent='SampleBrowser/2.0')

    def test_row_content(self):
        row = self.row_a
        self.assertEqual(row.version_id, self.v1)
        self.assertEqual(row.document_id, self.doc)
        self.assertEqual(row.user_id, self.portal_a)
        self.assertEqual(row.partner_id, self.portal_a.partner_id)
        self.assertTrue(row.accepted_at)
        self.assertEqual(row.ip, '192.0.2.10')
        self.assertEqual(row.user_agent, 'SampleBrowser/1.0')

    def test_draft_cannot_be_accepted(self):
        v2 = self._new_version('<p>Draft.</p>')
        with self.assertRaises(UserError):
            v2._portal_consent_accept(self.portal_a)

    def test_never_edited(self):
        with self.assertRaises(UserError):
            self.row_a.ip = '198.51.100.1'
        with self.assertRaises(UserError):
            self.row_a.with_user(self.manager).write({'ip': '198.51.100.1'})

    def test_deletion(self):
        with self.assertRaises(AccessError):
            self.row_a.with_user(self.manager).unlink()
        self.assertEqual(len(self.Acceptance.with_user(self.manager).search([('version_id', '=', self.v1.id)])), 2)
        self.row_b.unlink()  # administrator (superuser in the test env)
        self.assertFalse(self.row_b.exists())

    def test_portal_reads_own_rows_only(self):
        rows = self.Acceptance.with_user(self.portal_a).search([])
        self.assertEqual(rows, self.row_a)
        with self.assertRaises(AccessError):
            self.row_b.with_user(self.portal_a).read(['ip'])
        with self.assertRaises(AccessError):
            self.Acceptance.with_user(self.portal_a).create({
                'version_id': self.v1.id, 'user_id': self.portal_a.id})
