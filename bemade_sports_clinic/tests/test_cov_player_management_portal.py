from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovPlayerManagementPortal(PortalCovCommon):
    """GET-route coverage for the player-management portal controller."""

    def test_create_player_form(self):
        self._login_tp()
        resp = self.url_open(f'/my/player/create?team_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)

    def test_edit_player_form(self):
        self._login_tp()
        resp = self.url_open(f'/my/player/edit?patient_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)

    def test_add_contact_form(self):
        self._login_tp()
        resp = self.url_open(f'/my/player/contact/add?patient_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)

    def test_edit_contact_form(self):
        self._login_tp()
        resp = self.url_open(f'/my/player/contact/edit?contact_id={self.contact.id}')
        self.assertEqual(resp.status_code, 200)
