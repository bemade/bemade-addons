# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Test helpers. Synthetic content only (made-up users and texts)."""
from contextlib import contextmanager
from unittest.mock import patch

from odoo.fields import Command
from odoo.tests import new_test_user


def consent_frontend_langs(env, default='en_US', others=()):
    """The frontend languages a test asserts, whatever the database's site
    is set to (a consumer's site may default to French): ``default`` (and
    ``others``) activated, ``default`` the frontend default (every website's
    and the partners' default ``lang``), ``others`` added to every website.
    Call it before creating the test users. Undone with the rollback."""
    langs = env['res.lang']
    for code in (default, *others):
        langs |= langs._activate_lang(code)
    if 'website' in env:
        for website in env['website'].search([]):
            website.write({
                'language_ids': [Command.link(lang.id) for lang in langs],
                'default_lang_id': langs.filtered(lambda lang: lang.code == default).id,
            })
    env['ir.default'].set('res.partner', 'lang', default)
    env.flush_all()
    env.registry.clear_cache()
    return langs


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
