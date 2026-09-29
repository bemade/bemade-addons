"""Task 1544 — document delete is POST + CSRF; activity routes enforce CSRF (AC3).

Use case: a crafted link, image or cross-site form must not delete a document
or create / change / complete / cancel / reassign an activity on behalf of a
logged-in portal user.

Acceptance criteria:
- ``GET /my/injury/document/delete/<id>`` is refused (405/404) and deletes
  nothing; a POST without a CSRF token is refused (400); a POST with the token
  deletes the document (TP).
- ``/my/activity/save``, ``update``, ``complete``, ``cancel`` and
  ``reassign`` refuse a POST without ``csrf_token`` and change nothing; with
  the token they work.
- The pages that post to these routes carry a ``csrf_token`` input in every
  such form.

All fixtures are synthetic.
"""
import base64
import re

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestPortalCsrf1544(PortalCovCommon):

    def _new_document(self):
        return self.env['sports.injury.document'].create({
            'name': 'zz-1544.pdf', 'patient_id': self.player.id,
            'injury_id': self.injury.id,
            'file_content': base64.b64encode(b'synthetic'), 'category': 'other',
        })

    # -- document delete ---------------------------------------------------------

    @mute_logger('odoo.http')
    def test_document_delete_get_refused(self):
        doc = self._new_document()
        self._login_tp()
        resp = self.url_open('/my/injury/document/delete/%s' % doc.id)
        self.assertIn(resp.status_code, (404, 405))
        self.assertTrue(doc.exists())

    @mute_logger('odoo.http')
    def test_document_delete_post_without_token_refused(self):
        doc = self._new_document()
        self._login_tp()
        # (a non-empty body: url_open turns an empty one into a GET)
        resp = self.url_open('/my/injury/document/delete/%s' % doc.id,
                             data={'team_id': self.team_a.id})
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(doc.exists())

    def test_document_delete_post_with_token(self):
        doc = self._new_document()
        self._login_tp()
        resp = self.url_open('/my/injury/document/delete/%s' % doc.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertFalse(doc.exists())

    def test_documents_page_delete_is_post_form_with_token(self):
        self._new_document()
        self._login_tp()
        resp = self.url_open('/my/injury/documents?injury_id=%s' % self.injury.id)
        self.assertEqual(resp.status_code, 200)
        forms = re.findall(
            r'<form[^>]*action="/my/injury/document/delete/\d+"[^>]*>(.*?)</form>',
            resp.text, re.S)
        self.assertTrue(forms)
        for form in forms:
            self.assertIn('name="csrf_token"', form)
        self.assertNotRegex(resp.text, r'href="/my/injury/document/delete/')

    # -- activity routes ---------------------------------------------------------

    def _activity_posts(self):
        return {
            '/my/activity/save': {
                'model': 'sports.patient', 'res_id': self.player.id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': 'ZZ 1544 new', 'user_id': self.tp.id,
                'date_deadline': '2026-12-31'},
            '/my/activity/update': {
                'activity_id': self.act_player.id,
                'activity_type_id': self.act_player.activity_type_id.id,
                'summary': 'ZZ 1544 updated',
                'date_deadline': str(self.act_player.date_deadline)},
            '/my/activity/reassign': {
                'activity_id': self.act_team.id, 'new_user_id': self.coach.id},
            '/my/activity/complete': {'activity_id': self.act_event.id},
            '/my/activity/cancel': {'activity_id': self.act_injury.id},
        }

    @mute_logger('odoo.http')
    def test_activity_posts_without_token_refused(self):
        self._login_tp()
        Activity = self.env['mail.activity']
        for url, data in self._activity_posts().items():
            resp = self.url_open(url, data=data, allow_redirects=False)
            self.assertEqual(resp.status_code, 400, url)
        self.assertFalse(Activity.search_count([('summary', '=', 'ZZ 1544 new')]))
        self.act_player.invalidate_recordset()
        self.assertEqual(self.act_player.summary, 'Player task')
        self.assertEqual(self.act_team.user_id, self.tp)
        self.assertTrue(self.act_event.exists() and self.act_event.active)
        self.assertTrue(self.act_injury.exists())

    def test_activity_posts_with_token_work(self):
        self._login_tp()
        Activity = self.env['mail.activity']
        for url, data in self._activity_posts().items():
            resp = self.url_open(url, data=dict(data, csrf_token=self._csrf()),
                                 allow_redirects=False)
            self.assertIn(resp.status_code, (302, 303), url)
        self.assertEqual(Activity.search_count([('summary', '=', 'ZZ 1544 new')]), 1)
        self.act_player.invalidate_recordset()
        self.assertEqual(self.act_player.summary, 'ZZ 1544 updated')
        self.act_team.invalidate_recordset()
        self.assertEqual(self.act_team.user_id, self.coach)
        # Completed: removed, or archived as done (activity type keep_done).
        self.assertFalse(self.act_event.exists() and self.act_event.active)
        self.assertFalse(self.act_injury.exists())

    def test_activity_forms_carry_token(self):
        """Every form posting to an activity route on the pages that show them
        carries a csrf_token input (the routes now enforce it)."""
        self._login_tp()
        pages = [
            '/my/activities',
            '/my/player?player_id=%s' % self.player.id,
            '/my/team/%s' % self.team_a.id,
            '/my/activity/%s' % self.act_player.id,
            '/my/activity/%s/edit' % self.act_player.id,
            '/my/activity/create?model=sports.patient&res_id=%s' % self.player.id,
        ]
        seen = 0
        for page in pages:
            resp = self.url_open(page)
            self.assertEqual(resp.status_code, 200, page)
            for attrs, body in re.findall(
                    r'<form([^>]*action="/my/activity/(?:save|update|complete|cancel|reassign)"'
                    r'[^>]*)>(.*?)</form>', resp.text, re.S):
                seen += 1
                self.assertIn('name="csrf_token"', body, '%s: %s' % (page, attrs))
        self.assertGreater(seen, 3, 'fixture: the pages must show activity forms')
