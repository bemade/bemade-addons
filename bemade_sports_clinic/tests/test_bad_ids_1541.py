"""Task 1541 review (2026-11-26, pre-test F1 / F2) — an old bookmark or an
edited URL with a missing, empty, malformed or unknown id never answers a 500
nor loops. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-F1 A missing or empty id on an old bookmark lands on the players list
  (a redirect); a malformed (``abc``) or unknown id is « not found » (404) —
  ``/my/player/edit`` (``patient_id`` or ``player_id``), ``/my/player/contact/
  add``, ``/my/player/contact/edit``, ``/my/injury/edit``,
  ``/my/injury/activities``, and the live ``/my/player``. A malformed team
  filter / context is ignored (the page still renders).
* UC-F2 An event that does not exist is « not found »: ``/my/event/<id>/edit``
  → 301 → ``/my/event/<id>`` → 404, no redirect loop.
"""
from urllib.parse import urlsplit

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.portal_cov_common import PortalCovCommon


@tagged('post_install', '-at_install')
class TestBadIds1541(PortalCovCommon):

    def _status(self, url):
        resp = self.url_open(url, allow_redirects=False)
        location = resp.headers.get('Location')
        return resp.status_code, location and urlsplit(location).path

    def _cases(self):
        pid = self.player.id
        return [
            # (url, expected status, expected Location path or None)
            ('/my/player/edit', 303, '/my/players'),
            ('/my/player/edit?player_id=', 303, '/my/players'),
            ('/my/player/edit?patient_id=', 303, '/my/players'),
            ('/my/player/edit?patient_id=abc', 404, None),
            ('/my/player/edit?player_id=abc', 404, None),
            ('/my/player/edit?player_id=%s' % pid, 301, '/my/player'),
            ('/my/player/contact/add', 303, '/my/players'),
            ('/my/player/contact/add?patient_id=abc', 404, None),
            ('/my/player/contact/edit', 303, '/my/players'),
            ('/my/player/contact/edit?contact_id=abc', 404, None),
            ('/my/player/contact/edit?contact_id=999999999', 404, None),
            ('/my/injury/edit', 303, '/my/players'),
            ('/my/injury/edit?injury_id=abc', 404, None),
            ('/my/injury/activities?injury_id=abc', 404, None),
            ('/my/player', 303, '/my/players'),
            ('/my/player?player_id=', 303, '/my/players'),
            ('/my/player?player_id=abc', 404, None),
            ('/my/player?player_id=999999999', 404, None),
            ('/my/player?player_id=%s&team_id=abc' % pid, 200, None),
            ('/my/events?team_id=abc&organization_id=x&assigned_user_id=y', 200, None),
            ('/my/event?event_id=abc', 404, None),
            ('/my/event?event_id=', 303, '/my/events'),
            ('/my/events/calendar?team_id=abc', 200, None),
            ('/my/event?event_id=999999999', 404, None),
            ('/my/event/999999999', 404, None),
        ]

    def test_bad_ids_never_500(self):
        self._login_tp()
        for url, status, location in self._cases():
            with self.subTest(url=url):
                got_status, got_location = self._status(url)
                self.assertNotEqual(got_status, 500, url)
                self.assertEqual(got_status, status, url)
                if location:
                    self.assertEqual(got_location, location, url)

    def test_missing_event_edit_no_loop(self):
        self._login_tp()
        status, location = self._status('/my/event/999999999/edit')
        self.assertEqual((status, location), (301, '/my/event/999999999'))
        # Followed: one hop, then « not found » — no redirect to itself.
        resp = self.url_open('/my/event/999999999/edit')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(len(resp.history), 1)
