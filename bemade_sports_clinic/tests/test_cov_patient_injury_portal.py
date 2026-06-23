from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovPatientInjuryPortal(PortalCovCommon):
    """GET-route coverage for the patient-injury portal controller."""

    def test_create_injury_form(self):
        self._login_coach()
        resp = self.url_open(f'/my/patient/injury/new?patient_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)

    def test_edit_injury_form(self):
        self._login_tp()
        resp = self.url_open(f'/my/injury/edit?injury_id={self.injury.id}')
        self.assertEqual(resp.status_code, 200)

    def test_view_treatment_notes(self):
        self._login_tp()
        resp = self.url_open(f'/my/patient/notes?patient_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)

    def test_view_injury_documents(self):
        self._login_tp()
        resp = self.url_open(f'/my/injury/documents?injury_id={self.injury.id}')
        self.assertEqual(resp.status_code, 200)
