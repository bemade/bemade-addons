import base64

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

    def _new_document(self):
        return self.env['sports.injury.document'].create({
            'name': 'fixture.pdf', 'patient_id': self.player.id, 'injury_id': self.injury.id,
            'file_content': base64.b64encode(b'fixture-bytes'), 'category': 'other',
        })

    # ---- document upload / download / delete ----

    def test_upload_injury_document_happy(self):
        self._login_tp()
        before = self.env['sports.injury.document'].search_count([('injury_id', '=', self.injury.id)])
        resp = self.url_open(
            '/my/injury/document/upload',
            data={'csrf_token': self._csrf(), 'injury_id': self.injury.id},
            files={'attachment': ('report.pdf', b'%PDF-1.4 test', 'application/pdf')})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.env['sports.injury.document'].search_count([('injury_id', '=', self.injury.id)]),
            before + 1)

    def test_upload_injury_document_no_file(self):
        self._login_tp()
        before = self.env['sports.injury.document'].search_count([('injury_id', '=', self.injury.id)])
        resp = self.url_open('/my/injury/document/upload',
                             data={'csrf_token': self._csrf(), 'injury_id': self.injury.id})
        self.assertEqual(resp.status_code, 200)  # redirected back with ?error=no_file
        self.assertEqual(
            self.env['sports.injury.document'].search_count([('injury_id', '=', self.injury.id)]),
            before, "no document should be created without a file")

    def test_download_injury_document(self):
        doc = self._new_document()
        self._login_tp()
        resp = self.url_open('/my/injury/document/download/%s' % doc.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'fixture-bytes')

    def test_delete_injury_document_happy(self):
        doc = self._new_document()
        self._login_tp()
        resp = self.url_open('/my/injury/document/delete/%s' % doc.id)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(doc.exists(), "TP should be able to delete the document")

    def test_delete_injury_document_denied_for_coach(self):
        doc = self._new_document()
        self._login_coach()
        self.url_open('/my/injury/document/delete/%s' % doc.id)
        self.assertTrue(doc.exists(), "a coach must not delete injury documents")

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

    # ---- edit_injury_submit ----

    def test_edit_injury_submit_happy(self):
        injury = self._new_injury(stage='active')
        self._login_tp()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': injury.id,
            'diagnosis': 'Edited Diagnosis', 'external_notes': 'updated note',
        })
        self.assertEqual(resp.status_code, 200)
        injury.invalidate_recordset(['diagnosis'])
        self.assertEqual(injury.diagnosis, 'Edited Diagnosis')
