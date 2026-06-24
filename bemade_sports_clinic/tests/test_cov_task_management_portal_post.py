from datetime import date

from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovTaskManagementPortalPost(PortalCovCommon):
    """POST-route sampling for the task/activity portal (activity actions)."""

    def test_complete_activity(self):
        # NOTE: only asserts the route handles the request without error. The
        # post-completion state (whether action_feedback unlinks the activity) is
        # version-dependent and not asserted here.
        self._login_tp()
        resp = self.url_open('/my/activity/complete', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_injury.id, 'feedback': 'done',
        })
        self.assertEqual(resp.status_code, 200)

    def test_cancel_activity(self):
        self._login_tp()
        resp = self.url_open('/my/activity/cancel', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_team.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.act_team.exists(), "cancelling should delete the activity")

    def test_reschedule_activity(self):
        self._login_tp()
        resp = self.url_open('/my/activity/reschedule', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_player.id,
            'new_deadline': '2026-12-31',
        })
        self.assertEqual(resp.status_code, 200)
        self.act_player.invalidate_recordset(['date_deadline'])
        self.assertEqual(self.act_player.date_deadline, date(2026, 12, 31))

    def test_reschedule_activity_missing_deadline(self):
        self._login_tp()
        original = self.act_player.date_deadline
        self.url_open('/my/activity/reschedule', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_player.id,
        })
        self.act_player.invalidate_recordset(['date_deadline'])
        self.assertEqual(self.act_player.date_deadline, original, "no deadline -> no change")

    def test_reassign_activity_rejects_non_tp(self):
        # The coach is not a treatment professional, so reassignment must be refused.
        self._login_tp()
        self.url_open('/my/activity/reassign', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_event.id,
            'new_user_id': self.coach.id,
        })
        self.act_event.invalidate_recordset(['user_id'])
        self.assertEqual(self.act_event.user_id, self.tp,
                         "reassigning to a non-TP must be rejected")

    def test_create_activity_submit_happy(self):
        self._login_tp()
        resp = self.url_open('/my/activity/save', data={
            'csrf_token': self._csrf(),
            'model': 'sports.patient', 'res_id': self.player.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Created Activity', 'user_id': self.tp.id,
            'date_deadline': '2026-12-31',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.env['mail.activity'].search([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id),
            ('summary', '=', 'Created Activity')]),
            "the activity should have been created")

    def test_create_activity_submit_missing_fields(self):
        self._login_tp()
        before = self.env['mail.activity'].search_count([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id)])
        resp = self.url_open('/my/activity/save', data={
            'csrf_token': self._csrf(),
            'model': 'sports.patient', 'res_id': self.player.id,
            'summary': 'No type/user/deadline',  # missing required fields
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.env['mail.activity'].search_count([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id)]),
            before, "no activity should be created when required fields are missing")
