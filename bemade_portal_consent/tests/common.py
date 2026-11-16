# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Test helpers. Synthetic content only (made-up users and texts)."""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests import new_test_user


@contextmanager
def consent_hook(env, documents_for):
    """Swap ``res.users._portal_consent_documents`` for the duration of the
    block: ``documents_for(user)`` returns the documents ``user`` must
    accept (a ``portal.consent.document`` recordset, any env). The patch is
    on the registry class, so the HTTP server thread of an HttpCase sees
    it too."""
    cls = type(env['res.users'])

    def patched(self):
        self.ensure_one()
        docs = documents_for(self)
        return self.env['portal.consent.document'].browse(docs.ids)

    with patch.object(cls, '_portal_consent_documents', patched):
        yield


class ConsentFixtures:
    """Mixin for the test classes: a synthetic document, its draft v1 and
    a few users."""

    @classmethod
    def _consent_setup(cls):
        env = cls.env
        cls.Document = env['portal.consent.document']
        cls.Version = env['portal.consent.version']
        cls.Acceptance = env['portal.consent.acceptance']
        cls.doc = cls.Document.create({
            'name': 'Sample privacy notice',
            'code': 'tc5390_privacy',
        })
        cls.v1 = cls.Version.create({
            'document_id': cls.doc.id,
            'body': '<p>Sample notice, first text.</p>',
        })
        cls.portal_a = new_test_user(env, login='tc5390_portal_a', groups='base.group_portal')
        cls.portal_b = new_test_user(env, login='tc5390_portal_b', groups='base.group_portal')
        cls.staff = new_test_user(env, login='tc5390_staff', groups='base.group_user')

    @classmethod
    def _new_version(cls, body, document=None):
        return cls.Version.create({
            'document_id': (document or cls.doc).id,
            'body': body,
        })
