"""Task 1612 — verifying an injury from the app (status selector, the save
route ``stage`` unverified → active) does what the « Verify » button does.
Synthetic fixtures only.

Use case: a therapist opens an unverified injury in the app and switches its
status to « Active ». Before 1612 the stage changed but the « Vérifier la
blessure » To-Do stayed open (clock / overdue count unchanged) and no
« Injury verified by … » message was logged.

Acceptance criteria:

* AC1 The app save unverified → active closes the injury's open
  verification To-Do and posts « Injury verified by <user> » on the injury.
* AC2 The « Verify » button path (``action_verify_injury``) is unchanged:
  same closing, same message, still refused on a non-unverified injury.
* AC3 Other stage saves (active → resolved, …) post no verification message
  and leave other activities alone.
"""
from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient_injury import VERIFY_INJURY_SUMMARY
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellInjuryVerify1612(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.unverified = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic strain',
        })
        cls.unverified.with_context(mail_notrack=True).write({'stage': 'unverified'})
        cls.todo = env['mail.activity'].create({
            'res_model_id': env['ir.model']._get('sports.patient').id,
            'res_id': cls.player.id,
            'injury_id': cls.unverified.id,
            'activity_type_id': env.ref('mail.mail_activity_data_todo').id,
            'summary': '[Injury: Synthetic strain] ' + VERIFY_INJURY_SUMMARY,
            'user_id': cls.tp.id,
            'date_deadline': fields.Date.today(),
        })

    def _wd(self, record):
        record.invalidate_recordset()
        return fields.Datetime.to_string(record.write_date)

    def _save(self, record, field, value):
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value, 'write_date': self._wd(record),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)

    def _open_verify_todos(self, injury):
        return self.env['mail.activity'].search(
            injury._verify_activity_domain() + [('active', '=', True)])

    def _verified_messages(self, injury):
        return injury.message_ids.filtered(
            lambda m: 'Injury verified by' in (m.body or ''))

    # -- AC1 -------------------------------------------------------------
    def test_app_verify_closes_todo_and_logs(self):
        self.assertEqual(self._open_verify_todos(self.unverified), self.todo)
        self._login_tp()
        resp = self._save(self.unverified, 'stage', 'active')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.unverified.invalidate_recordset()
        self.assertEqual(self.unverified.stage, 'active')
        self.assertFalse(self._open_verify_todos(self.unverified),
                         "the « Verify injury » To-Do is closed")
        msgs = self._verified_messages(self.unverified)
        self.assertEqual(len(msgs), 1)
        self.assertIn('PC TP', msgs.body)
        # An unrelated activity about the same injury stays open.
        self.assertTrue(self.act_injury.exists() and self.act_injury.active)

    # -- AC2 -------------------------------------------------------------
    def test_button_path_unchanged(self):
        self.unverified.with_user(self.tp).action_verify_injury()
        self.assertEqual(self.unverified.stage, 'active')
        self.assertFalse(self._open_verify_todos(self.unverified))
        self.assertEqual(len(self._verified_messages(self.unverified)), 1)
        with self.assertRaises(UserError):
            self.unverified.with_user(self.tp).action_verify_injury()

    # -- AC3 -------------------------------------------------------------
    def test_other_stage_saves_no_verification(self):
        self._login_tp()
        resp = self._save(self.injury, 'stage', 'resolved')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse(self._verified_messages(self.injury))
        self.assertTrue(self.todo.active, "another injury's To-Do is untouched")
