from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovPlayerManagementPortalPost(PortalCovCommon):
    """POST-route sampling for the player-management portal (contacts + player create)."""

    # ---- add_contact_submit ----

    def test_add_contact_happy(self):
        self._login_tp()
        before = len(self.player.contact_ids)
        resp = self.url_open('/my/player/contact/save', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id,
            'name': 'Emergency Mom', 'contact_type': 'mother', 'mobile': '5145550000',
        })
        self.assertEqual(resp.status_code, 200)
        self.player.invalidate_recordset(['contact_ids'])
        self.assertEqual(len(self.player.contact_ids), before + 1)

    def test_add_contact_unauthorized(self):
        self._login_plain()
        resp = self.url_open('/my/player/contact/save', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id, 'name': 'X', 'contact_type': 'mother',
        })
        self.assertEqual(resp.status_code, 403)

    # ---- delete_contact ----

    def test_delete_contact_happy(self):
        self._login_tp()
        resp = self.url_open('/my/player/contact/delete', data={
            'csrf_token': self._csrf(), 'contact_id': self.contact.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.contact.exists(), "TP should be able to delete a contact")

    def test_delete_contact_denied_for_coach(self):
        self._login_coach()
        self.url_open('/my/player/contact/delete', data={
            'csrf_token': self._csrf(), 'contact_id': self.contact.id,
        })
        self.assertTrue(self.contact.exists(), "a coach must not delete emergency contacts")

    # ---- create_player_submit ----

    def test_create_player_happy(self):
        self._login_tp()
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(),
            'first_name': 'Standalone', 'last_name': 'Created',
            'date_of_birth': '2004-04-04', 'team_ids': self.team_a.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.env['sports.patient'].search([
            ('first_name', '=', 'Standalone'), ('last_name', '=', 'Created')]),
            "the player should have been created")

    def test_create_player_missing_names(self):
        self._login_tp()
        before = self.env['sports.patient'].search_count([])
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': '', 'last_name': '',
        })
        self.assertEqual(resp.status_code, 200)  # redirected back to the form
        self.assertEqual(self.env['sports.patient'].search_count([]), before,
                         "no player should be created without names")
