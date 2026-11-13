# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5371 (kit P4c1): the toast, its session notification and the undo
move to the kit.

* UC-N1 ``PortalKitApp._pk_pop_notification()`` pops
  ``session['notification']`` (the ``{type, title, message[, undo_url]}``
  dict a POST route stores) into ``{id, message, title, tone, undo_url}``:
  tone ``error`` for the danger / warning / error types, ``success``
  otherwise; a 16-hex one-time id; ``Cache-Control: no-store`` on the page.
  An empty or malformed notification is False.
* UC-N2 A fragment request (``X-Pk-Fragments``) leaves it for the next page;
  a guarded form's fetch (``X-Pk-Guard``) peeks at it (the page carries it,
  the session keeps it, the response is not marked no-store).
* UC-N3 Only a same-site undo URL (``/path``, never ``//host`` or an
  absolute URL) is kept.
* UC-N4 ``PortalKitApp._pk_offer_undo(message, undo_url)`` stores a success
  notification carrying ``undo_url``.
* UC-N5 ``bemade_portal_kit.pk_toast_host`` renders the toast host from a
  ``pk_notification`` (``data-pk-notify``, ``-title`` only with a message,
  ``-tone``, ``-id``; an error also carries ``data-pk-flash-error``) and,
  with an undo URL, the hidden restore form ``form[data-pk-undo]``
  (« Undo », CSRF). Without a notification: an empty, hidden toast.
* UC-N6 ``pk_toast`` is the kit's, in its runtime bundle and the hoot setup.
Synthetic fixtures only.
"""
import re
from unittest.mock import MagicMock, patch

from lxml import html as lxml_html

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.controllers import pk_app
from odoo.addons.bemade_portal_kit.controllers.pk_app import PortalKitApp

KIT = 'bemade_portal_kit'


def _fake_request(session, headers=None):
    fake = MagicMock()
    fake.httprequest.headers = headers or {}
    fake.session = session
    fake.future_response.headers = {}
    return fake


@tagged('post_install', '-at_install')
class TestPkToast(TransactionCase):

    def _pop(self, notification, headers=None):
        session = {} if notification is None else {'notification': notification}
        fake = _fake_request(session, headers)
        with patch.object(pk_app, 'request', fake):
            result = PortalKitApp._pk_pop_notification()
        return result, session, fake.future_response.headers

    def test_pop_shape_and_tone(self):
        result, session, headers = self._pop({'type': 'success', 'title': 'Team', 'message': 'Added'})
        self.assertEqual(set(result), {'id', 'message', 'title', 'tone', 'undo_url'})
        self.assertEqual((result['message'], result['title'], result['tone']), ('Added', 'Team', 'success'))
        self.assertRegex(result['id'], r'^[0-9a-f]{16}$')
        self.assertFalse(result['undo_url'])
        self.assertNotIn('notification', session, 'popped: shown once')
        self.assertEqual(headers.get('Cache-Control'), 'no-store')
        for kind in ('danger', 'warning', 'error'):
            self.assertEqual(self._pop({'type': kind, 'message': 'No'})[0]['tone'], 'error', kind)
        self.assertEqual(self._pop({'type': 'info', 'message': 'Yes'})[0]['tone'], 'success')
        self.assertNotEqual(self._pop({'message': 'A'})[0]['id'], self._pop({'message': 'A'})[0]['id'])

    def test_pop_empty(self):
        self.assertFalse(self._pop(None)[0])
        self.assertFalse(self._pop({'type': 'success', 'message': '', 'title': ''})[0])
        self.assertFalse(self._pop('a string')[0])

    def test_fragment_request_leaves_it(self):
        result, session, headers = self._pop({'message': 'Later'}, {'X-Pk-Fragments': 'page:x:y'})
        self.assertFalse(result)
        self.assertIn('notification', session)
        self.assertNotIn('Cache-Control', headers)

    def test_guard_probe_peeks(self):
        result, session, headers = self._pop({'type': 'danger', 'message': 'Refused'}, {'X-Pk-Guard': '1'})
        self.assertEqual(result['message'], 'Refused')
        self.assertIn('notification', session, 'the real navigation still shows it')
        self.assertNotIn('Cache-Control', headers)

    def test_undo_url_same_site_only(self):
        good = self._pop({'message': 'Archived', 'undo_url': '/pk/t/restore?x=1'})[0]
        self.assertEqual(good['undo_url'], '/pk/t/restore?x=1')
        for bad in ('//evil.example/x', 'https://evil.example/x', 'javascript:x', 42):
            self.assertFalse(self._pop({'message': 'Archived', 'undo_url': bad})[0]['undo_url'], bad)

    def test_offer_undo(self):
        session = {}
        with patch.object(pk_app, 'request', _fake_request(session)):
            PortalKitApp._pk_offer_undo('Thing archived.', '/pk/t/restore/3')
        self.assertEqual(session['notification'], {
            'type': 'success', 'title': '', 'message': 'Thing archived.', 'undo_url': '/pk/t/restore/3',
        })

    def _render(self, notification):
        fake = MagicMock()
        fake.csrf_token.return_value = 'pk-t-token'
        html = self.env['ir.qweb'].with_context(minimal_qcontext=True)._render(
            '%s.pk_toast_host' % KIT, {'pk_notification': notification, 'request': fake})
        return lxml_html.fragment_fromstring(str(html), create_parent='div')

    def test_host_renders_notification(self):
        root = self._render({'id': 'abc', 'message': 'Added', 'title': 'Team', 'tone': 'success',
                             'undo_url': False})
        toast = root.xpath('.//*[contains(@class, "o_pk_toast")]')
        self.assertEqual(len(toast), 1)
        toast = toast[0]
        self.assertEqual(toast.get('hidden'), 'hidden')
        self.assertEqual(toast.get('role'), 'status')
        self.assertEqual(toast.get('data-pk-notify'), 'Added')
        self.assertEqual(toast.get('data-pk-notify-title'), 'Team')
        self.assertEqual(toast.get('data-pk-notify-tone'), 'success')
        self.assertEqual(toast.get('data-pk-notify-id'), 'abc')
        self.assertIsNone(toast.get('data-pk-flash-error'))
        self.assertFalse(root.xpath('.//form'))
        markup = lxml_html.tostring(root, encoding='unicode')
        self.assertNotRegex(markup, re.compile(r'data-sc-'))

    def test_host_title_only_and_error(self):
        toast = self._render({'id': 'e1', 'message': '', 'title': 'Refused', 'tone': 'error',
                              'undo_url': False}).xpath('.//*[contains(@class, "o_pk_toast")]')[0]
        self.assertEqual(toast.get('data-pk-notify'), 'Refused')
        self.assertIsNone(toast.get('data-pk-notify-title'))
        self.assertEqual(toast.get('data-pk-flash-error'), 'Refused')

    def test_host_undo_form(self):
        root = self._render({'id': 'u1', 'message': 'Note archived.', 'title': '', 'tone': 'success',
                             'undo_url': '/pk/t/restore/3'})
        form = root.xpath('.//form[@data-pk-undo]')
        self.assertEqual(len(form), 1)
        form = form[0]
        self.assertEqual(form.get('action'), '/pk/t/restore/3')
        self.assertEqual(form.get('method'), 'post')
        self.assertEqual(form.get('hidden'), 'hidden')
        self.assertEqual(form.get('data-pk-toast-action'), 'Undo')
        self.assertEqual(form.xpath('.//input[@name="csrf_token"]/@value'), ['pk-t-token'])

    def test_host_without_notification(self):
        root = self._render(False)
        toast = root.xpath('.//*[contains(@class, "o_pk_toast")]')[0]
        self.assertIsNone(toast.get('data-pk-notify'))
        self.assertFalse(root.xpath('.//form'))

    def test_script_bundled(self):
        assets = get_manifest(KIT)['assets']
        path = '%s/static/src/js/pk_toast.js' % KIT
        self.assertIn(path, assets['web.assets_frontend'])
        self.assertIn(path, assets['web.assets_unit_tests_setup'])
