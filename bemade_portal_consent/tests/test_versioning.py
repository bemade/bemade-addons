# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Versioning.

Acceptance criteria
-------------------
* A new version is a draft, numbered 1, 2, 3… per document.
* Publishing sets the state, the date and the publisher, and locks the
  version: its body (and its number, its document, its resign flag) can no
  longer be written; a published version cannot be deleted.
* The text's translations are locked too: a draft's text is translated
  (term by term) before publishing; a published one's no longer.
* The first published version of a document always requires a new
  acceptance, whatever was asked.
* The required version of a document is its latest published version that
  requires a new acceptance; a version published without it does not move
  the required version.
* A version older than the latest published one cannot be published.
* A document with no published version has no required version.
* The document code is unique.
"""
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from .common import ConsentFixtures


@tagged('post_install', '-at_install')
class TestConsentVersioning(ConsentFixtures, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._consent_setup()

    def test_numbering_and_draft(self):
        v2 = self._new_version('<p>Second text.</p>')
        self.assertEqual((self.v1.number, v2.number), (1, 2))
        self.assertEqual(v2.state, 'draft')
        self.assertFalse(self.doc.required_version_id)

    def test_publish_locks(self):
        self.v1._portal_consent_publish(requires_resign=False)
        self.assertEqual(self.v1.state, 'published')
        self.assertTrue(self.v1.published_at)
        self.assertEqual(self.v1.published_by_id, self.env.user)
        self.assertTrue(self.v1.requires_resign, 'the first published version always requires')
        with self.assertRaises(UserError):
            self.v1.body = '<p>Changed after publication.</p>'
        with self.assertRaises(UserError):
            self.v1.requires_resign = False
        with self.assertRaises(UserError):
            self.v1.unlink()
        with self.assertRaises(UserError):
            self.v1._portal_consent_publish(requires_resign=True)

    def test_published_translations_locked(self):
        self.env['res.lang']._activate_lang('fr_FR')
        self.v1.update_field_translations('body', {'fr_FR': {'Sample notice, first text.': 'Avis fictif, premier texte.'}})
        self.assertIn('premier texte', self.v1.with_context(lang='fr_FR').body)
        self.v1._portal_consent_publish(requires_resign=True)
        with self.assertRaises(UserError):
            self.v1.update_field_translations('body', {'fr_FR': {'Sample notice, first text.': 'Autre texte.'}})
        with self.assertRaises(UserError):
            self.v1.with_context(lang='fr_FR').body = '<p>Autre texte.</p>'
        self.assertIn('premier texte', self.v1.with_context(lang='fr_FR').body)

    def test_draft_editable_and_deletable(self):
        v2 = self._new_version('<p>Draft.</p>')
        v2.body = '<p>Draft, reworded.</p>'
        self.assertIn('reworded', v2.body)
        v2.unlink()

    def test_required_version_follows_resign(self):
        self.v1._portal_consent_publish(requires_resign=True)
        self.assertEqual(self.doc.required_version_id, self.v1)
        v2 = self._new_version('<p>Typo fixed.</p>')
        v2._portal_consent_publish(requires_resign=False)
        self.assertEqual(self.doc.required_version_id, self.v1)
        self.assertEqual(self.doc.current_version_id, v2)
        v3 = self._new_version('<p>New purpose added.</p>')
        v3._portal_consent_publish(requires_resign=True)
        self.assertEqual(self.doc.required_version_id, v3)
        self.assertEqual(self.doc.current_version_id, v3)

    def test_no_publishing_an_older_draft(self):
        v2 = self._new_version('<p>Two.</p>')
        v3 = self._new_version('<p>Three.</p>')
        v3._portal_consent_publish(requires_resign=True)
        with self.assertRaises(UserError):
            v2._portal_consent_publish(requires_resign=True)

    def test_code_unique(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.Document.create({'name': 'Duplicate', 'code': 'tc5390_privacy'})
