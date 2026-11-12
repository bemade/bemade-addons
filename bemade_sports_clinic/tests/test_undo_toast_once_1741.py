"""Task 1741 — an archive's « … archived · Undo » / « … restored » message
never shows again on a later page (back chevron, browser back / forward, a
guarded form landing on its own page with a #fragment). Synthetic fixtures
only (this repository is public).

Cause (reproduced 2026-11-02 at 390 px on a prod-shaped copy: archive a
timesheet → « Annuler » → « Activités » tab → back): the page that carried
the session notification was replayed from the browser's cache with its
``data-sc-notify`` and showed it again.

Acceptance criteria:

* UC-1 A shell page that carries a session notification answers
  ``Cache-Control: no-store`` and gives the notification an id
  (``data-sc-notify-id``, a new one per notification); a page without one
  carries neither. The form guard's probe (X-Pk-Guard) peeks — no id
  consumed, the real page still shows it (task 1658 unchanged).
* UC-2 sc_app_ui.js shows a notification only on a « navigate » / « reload »
  load and once per id (sessionStorage); « Annuler » marks the session
  dirty before it posts (form.submit() fires no « submit » event).
* UC-3 pk_form_guard.js: a success target that differs from the page by its
  #fragment only reloads the page (was: a same-document navigation — the
  pending notification popped on a LATER page).
* UC-4 In a browser, phone 390 px: archive a quick note → « Undo » →
  « restored » once → another tab → back: no message
  (static/tests/tours/sc_undo_toast_once_1741_tours.js).
"""
from lxml import html as lxml_html

from odoo.tests import tagged
from odoo.tools.misc import file_open

from odoo.addons.bemade_sports_clinic.tests.test_card_top_bars_1736 import TopBars1736Common

LOGIN = 'pc.tp@example.com'


def _toast(tree):
    hosts = tree.xpath('//*[contains(@class, "o_pk_toast")]')
    return hosts[0] if hosts else None


@tagged('post_install', '-at_install')
class TestUndoToastOnce1741(TopBars1736Common):

    def test_notification_page_not_stored(self):
        self._login_tp()
        self._post('/my/notepad/%s/archive' % self.qnote.id, sc_undo='1')
        resp = self.url_open('/my/notepad')
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        tree = self._tree(resp.text)
        first = _toast(tree).get('data-sc-notify-id')
        self.assertTrue(first)
        self.assertTrue(tree.xpath('//form[@data-sc-form="sc.undo"]'))
        # Shown once: the next page has none, and is not « no-store ».
        resp = self.url_open('/my/notepad')
        self.assertNotEqual(resp.headers.get('Cache-Control'), 'no-store')
        self.assertIsNone(_toast(self._tree(resp.text)).get('data-sc-notify-id'))
        # « Undo »: « Note restored. » is a session toast too (was a
        # ?success= banner), with a NEW id.
        undo = '/my/notepad/%s/restore?undo=1' % self.qnote.id
        location = self._post(undo).headers['Location']
        self.assertNotIn('success=', location)
        resp = self.url_open('/my/notepad')
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        second = _toast(self._tree(resp.text)).get('data-sc-notify-id')
        self.assertEqual(_toast(self._tree(resp.text)).get('data-sc-notify'), 'Note restored.')
        self.assertTrue(second)
        self.assertNotEqual(first, second)

    def test_guard_probe_peeks(self):
        self._login_tp()
        self._post('/my/notepad/%s/archive' % self.qnote.id, sc_undo='1')
        resp = self.url_open('/my/notepad', headers={'X-Pk-Guard': '1'})
        self.assertTrue(_toast(self._tree(resp.text)).get('data-sc-notify'))
        resp = self.url_open('/my/notepad')
        self.assertTrue(_toast(self._tree(resp.text)).get('data-sc-notify'), 'the real page still shows it')

    def test_client_guards_present(self):
        with file_open('bemade_sports_clinic/static/src/js/sc_app_ui.js') as f:
            ui = f.read()
        self.assertIn('notifyNavigationType() === "back_forward" || notificationSeen(id)', ui)
        self.assertIn('markDirty();\n            undo.submit();', ui)
        with file_open('bemade_portal_kit/static/src/js/pk_form_guard.js') as f:
            guard = f.read()
        self.assertIn('window.location.reload();', guard)

    @staticmethod
    def _tree(text):
        return lxml_html.document_fromstring(text)


@tagged('post_install', '-at_install')
class TestUndoToastOnceTour1741(TopBars1736Common):
    browser_size = '390x844'

    def test_undo_toast_once(self):
        self.start_tour('/my/notepad', 'sc_1741_undo_toast_once', login=LOGIN)
        self.qnote.invalidate_recordset()
        self.assertTrue(self.qnote.active)
