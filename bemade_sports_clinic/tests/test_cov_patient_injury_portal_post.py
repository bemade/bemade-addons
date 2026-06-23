from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovPatientInjuryPortalPost(PortalCovCommon):
    """POST-route sampling for the patient-injury portal (create / verify / delete)."""

    def _new_injury(self, stage='unverified'):
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'team_id': self.team_a.id, 'diagnosis': 'Fixture',
        })
        injury.with_context(mail_notrack=True).write({'stage': stage})
        return injury

    # ---- create_injury_submit ----

    def test_create_injury_submit_happy(self):
        self._login_tp()
        before = self.env['sports.patient.injury'].search_count([('patient_id', '=', self.player.id)])
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id,
            'diagnosis': 'POST Created Injury',
            'injury_date': '2026-02-01',
        })
        self.assertEqual(resp.status_code, 200)  # followed redirect to player page
        after = self.env['sports.patient.injury'].search([
            ('patient_id', '=', self.player.id), ('diagnosis', '=', 'POST Created Injury'),
        ])
        self.assertTrue(after, "the injury should have been created")
        self.assertEqual(
            self.env['sports.patient.injury'].search_count([('patient_id', '=', self.player.id)]),
            before + 1)

    def test_create_injury_submit_unauthorized(self):
        # Plain portal user has no access to the patient -> 403, nothing created.
        self._login_plain()
        before = self.env['sports.patient.injury'].search_count([('patient_id', '=', self.player.id)])
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id,
            'diagnosis': 'Should Not Exist',
        })
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            self.env['sports.patient.injury'].search_count([('patient_id', '=', self.player.id)]),
            before, "no injury should be created for an unauthorized user")

    # ---- verify_injury ----

    def test_verify_injury_happy(self):
        injury = self._new_injury(stage='unverified')
        self._login_tp()
        resp = self.url_open('/my/injury/verify', data={
            'csrf_token': self._csrf(), 'injury_id': injury.id,
        })
        self.assertEqual(resp.status_code, 200)
        injury.invalidate_recordset(['stage'])
        self.assertEqual(injury.stage, 'active', "TP should be able to verify the injury")

    def test_verify_injury_denied_for_coach(self):
        # A coach is not a treatment professional -> verify must be refused.
        injury = self._new_injury(stage='unverified')
        self._login_coach()
        self.url_open('/my/injury/verify', data={
            'csrf_token': self._csrf(), 'injury_id': injury.id,
        })
        injury.invalidate_recordset(['stage'])
        self.assertEqual(injury.stage, 'unverified', "a coach must not be able to verify")

    # ---- delete_injury ----

    def test_delete_injury_happy(self):
        injury = self._new_injury(stage='active')
        self._login_tp()
        resp = self.url_open('/my/injury/delete', data={
            'csrf_token': self._csrf(), 'injury_id': injury.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(injury.exists(), "TP should be able to delete the injury")

    def test_delete_injury_denied_for_coach(self):
        injury = self._new_injury(stage='active')
        self._login_coach()
        self.url_open('/my/injury/delete', data={
            'csrf_token': self._csrf(), 'injury_id': injury.id,
        })
        self.assertTrue(injury.exists(), "a coach must not be able to delete the injury")
