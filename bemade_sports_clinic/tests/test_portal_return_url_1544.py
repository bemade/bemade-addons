"""Task 1544 — no open redirect through a posted ``return_url`` (AC3).

Use case: portal forms post a ``return_url`` so the user lands back where they
came from. A crafted form (or link) must not send the user to another site.

Acceptance criteria:
- ``_safe_return_url`` accepts same-site paths (``/my/…``) and refuses
  schemes, protocol-relative ``//host``, backslashes and control characters.
- The contact routes (add form, save, edit form, update, delete), the patient
  document upload and the activity update / reassign routes redirect to their
  fallback when ``return_url=https://evil.example`` (or ``//evil.example``),
  and honour a ``/my/…`` return URL.
- The contact add / edit forms and the activity create form never render an
  off-site or ``javascript:`` ``return_url`` (their Cancel link).

Note: core ``request.redirect(local=True)`` already strips scheme + host from
a redirect, so a posted ``https://evil.example/x`` used to land on the local
path ``/x`` rather than off-site; the helper now sends it to the fallback, and
the GET forms no longer echo it into a link.

All fixtures are synthetic.
"""
from odoo.tests import tagged

from ..controllers.access_control_mixin import AccessControlMixin
from .portal_cov_common import PortalCovCommon

EVIL = ('https://evil.example/x', '//evil.example/x', '/\\evil.example',
        '/\t/evil.example', 'javascript:alert(1)')


@tagged('-at_install', 'post_install')
class TestPortalReturnUrl1544(PortalCovCommon):

    # -- helper ----------------------------------------------------------------

    def test_safe_return_url_helper(self):
        safe = AccessControlMixin._safe_return_url
        for bad in EVIL + ('', None, 42, 'my/relative'):
            self.assertEqual(safe(bad, '/fallback'), '/fallback', repr(bad))
        for good in ('/my/player?player_id=3#contacts', '/my/players?search=Aa Bb',
                     '/my/clinic/4?patient=5'):
            self.assertEqual(safe(good, '/fallback'), good)

    # -- routes ----------------------------------------------------------------

    def _post(self, url, data):
        data = dict(data, csrf_token=self._csrf())
        return self.url_open(url, data=data, allow_redirects=False)

    def _assert_location(self, resp, expected_prefix):
        self.assertIn(resp.status_code, (301, 302, 303), resp.text[:300])
        location = resp.headers.get('Location', '')
        # werkzeug may absolutize the Location; compare on the path part.
        base = self.base_url()
        if location.startswith(base):
            location = location[len(base):]
        self.assertTrue(location.startswith(expected_prefix),
                        '%r does not start with %r' % (location, expected_prefix))
        self.assertNotIn('evil.example', location)

    def test_contact_save_and_update(self):
        self._login_tp()
        fallback = '/my/player?player_id=%s' % self.player.id
        for evil in EVIL:
            resp = self._post('/my/player/contact/save', {
                'patient_id': self.player.id, 'name': 'ZZ Contact',
                'contact_type': 'mother', 'return_url': evil})
            self._assert_location(resp, fallback)
            resp = self._post('/my/player/contact/update', {
                'contact_id': self.contact.id, 'name': 'Parent One',
                'contact_type': 'mother', 'return_url': evil})
            self._assert_location(resp, fallback)
        good = '/my/team/%s#players' % self.team_a.id
        resp = self._post('/my/player/contact/update', {
            'contact_id': self.contact.id, 'name': 'Parent One',
            'contact_type': 'mother', 'return_url': good})
        self._assert_location(resp, good)

    def test_contact_delete(self):
        self._login_tp()
        doomed = self.env['sports.patient.contact'].create({
            'patient_id': self.player.id, 'name': 'ZZ Doomed', 'contact_type': 'father'})
        resp = self._post('/my/player/contact/delete', {
            'contact_id': doomed.id, 'return_url': 'https://evil.example/x'})
        self._assert_location(resp, '/my/player?player_id=%s' % self.player.id)
        self.assertFalse(doomed.exists())

    def test_contact_forms_do_not_render_evil_url(self):
        """The GET forms render return_url as the Cancel link: an off-site or
        ``javascript:`` value must never reach the page (link-borne XSS)."""
        self._login_coach()
        for url in ('/my/player/contact/add?patient_id=%s&return_url=https://evil.example/x'
                    % self.player.id,
                    '/my/player/contact/add?patient_id=%s&return_url=javascript:alert(1544)'
                    % self.player.id,
                    '/my/player/contact/edit?contact_id=%s&return_url=//evil.example/x'
                    % self.contact.id,
                    '/my/activity/create?model=sports.patient&res_id=%s'
                    '&return_url=//evil.example/x' % self.player.id):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertNotIn('evil.example', resp.text)
            self.assertNotIn('alert(1544)', resp.text)

    def test_patient_document_upload(self):
        self._login_tp()
        resp = self.url_open('/my/patient/document/upload', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'return_url': 'https://evil.example/x',
        }, files={'attachment': ('zz.txt', b'synthetic', 'text/plain')},
            allow_redirects=False)
        self._assert_location(resp, '/my/player?player_id=%s' % self.player.id)
        good = '/my/clinic/1?patient=%s#clinic-documents' % self.player.id
        resp = self.url_open('/my/patient/document/upload', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'return_url': good,
        }, allow_redirects=False)
        self._assert_location(resp, '/my/clinic/1?patient=%s&error=no_file' % self.player.id)

    def test_activity_update_and_reassign(self):
        self._login_tp()
        resp = self._post('/my/activity/update', {
            'activity_id': self.act_player.id,
            'activity_type_id': self.act_player.activity_type_id.id,
            'summary': 'Player task', 'date_deadline': str(self.act_player.date_deadline),
            'return_url': 'https://evil.example/x'})
        self._assert_location(resp, '/my/activities')
        resp = self._post('/my/activity/reassign', {
            'activity_id': self.act_player.id, 'new_user_id': self.tp.id,
            'return_url': '//evil.example/x'})
        self._assert_location(resp, '/my/activities')
        resp = self._post('/my/activity/reassign', {
            'activity_id': self.act_player.id, 'new_user_id': self.tp.id,
            'return_url': '/my/player?player_id=%s' % self.player.id})
        self._assert_location(resp, '/my/player?player_id=%s' % self.player.id)
