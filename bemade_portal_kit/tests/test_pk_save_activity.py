# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5199 (P4a): the kit's ``mail.activity`` save spec.

The kit declares a generic spec for activities (summary, due date,
assignee, note) in ``portal.kit._pk_save_specs()``. Who may act on an
activity and to whom it may be assigned are two ``portal.kit`` hooks:

* ``_pk_activity_can_act(activity)``: default = the user's own write right
  on the activity (ACL + record rules);
* ``_pk_activity_assignable_users(activity)``: default = the internal users
  and the user themself.

Acceptance criteria (synthetic users and activities only):

* UC-AC1 With the defaults, an internal user reschedules an activity
  (``date_deadline``) and edits its summary / note / assignee; the answer is
  the read value and the display (the note as plain text, the assignee's
  name), ``refresh`` = the activity's own fragments, ``live_counts``.
* UC-AC2 A new due date in the past is refused (400, « The due date cannot be
  in the past. »); the stored past date re-saved is accepted; a blank
  summary or due date is refused; a malformed date is refused.
* UC-AC3 A portal user (no write right on activities) gets 403.
* UC-AC4 ``_pk_activity_can_act`` patched to refuse -> 403, nothing written;
  patched to allow a user without the ACL -> the write goes through
  (``sudo_write`` gated by the hook).
* UC-AC5 ``_pk_activity_assignable_users`` patched: an assignee outside it
  is refused (400), one inside it is saved.
"""
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import HttpCase, new_test_user, tagged

from .common import pk_csrf, pk_hook


@tagged('post_install', '-at_install')
class TestPkSaveActivity(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login='pk_act_user', groups='base.group_user,base.group_partner_manager',
                                 tz='America/Toronto')
        cls.other = new_test_user(cls.env, login='pk_act_other', groups='base.group_user')
        cls.portal = new_test_user(cls.env, login='pk_act_portal', groups='base.group_portal')
        cls.partner = cls.env['res.partner'].create({'name': 'Synthetic Activity Partner'})
        cls.activity = cls.env['mail.activity'].create({
            'res_model_id': cls.env['ir.model']._get_id('res.partner'),
            'res_id': cls.partner.id,
            'activity_type_id': cls.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Call back',
            'user_id': cls.user.id,
            'date_deadline': date.today() + timedelta(days=3),
        })

    def setUp(self):
        super().setUp()
        # Only the kit's own spec, whatever consumer is installed.
        kit_cls = type(self.env['portal.kit'])
        base = next(k for k in kit_cls.__mro__ if k.__dict__.get('_module') == 'bemade_portal_kit'
                    and '_pk_save_specs' in k.__dict__)
        hook = pk_hook(self.env, '_pk_save_specs', lambda _orig: base._pk_save_specs(self.env['portal.kit']))
        hook.__enter__()
        self.addCleanup(hook.__exit__, None, None, None)
        for name in ('_pk_activity_can_act', '_pk_activity_assignable_users'):
            patcher = patch.object(kit_cls, name, getattr(base, name))
            patcher.start()
            self.addCleanup(patcher.stop)

    def _post(self, field, value, login='pk_act_user', **extra):
        self.authenticate(login, login)
        self.activity.invalidate_recordset()
        return self.url_open('/my/app/save/mail.activity/%s' % self.activity.id, data={
            'field': field, 'value': value,
            'write_date': fields.Datetime.to_string(self.activity.write_date),
            'csrf_token': pk_csrf(self), **extra,
        }, allow_redirects=False)

    # -- UC-AC1 -----------------------------------------------------------
    def test_default_access_edits(self):
        day = fields.Date.to_string(date.today() + timedelta(days=10))
        res = self._post('date_deadline', day)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body['value'], day)
        self.assertTrue(body['display'])
        self.assertEqual(body['refresh'], ['mail.activity:%s:*' % self.activity.id])
        self.assertTrue(body['live_counts'])
        self.activity.invalidate_recordset()
        self.assertEqual(fields.Date.to_string(self.activity.date_deadline), day)

        body = self._post('summary', '  Call again ').json()
        self.assertEqual(body['value'], 'Call again')
        body = self._post('note', 'Line one').json()
        self.assertEqual((body['value'], body['display']), ('Line one', 'Line one'))
        self.activity.invalidate_recordset()
        self.assertIn('Line one', str(self.activity.note))
        body = self._post('user_id', str(self.other.id)).json()
        self.assertEqual((body['value'], body['display']), (self.other.id, self.other.name))

    # -- UC-AC2 -----------------------------------------------------------
    def test_refusals(self):
        yesterday = fields.Date.to_string(date.today() - timedelta(days=2))
        res = self._post('date_deadline', yesterday)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['message'], 'The due date cannot be in the past.')
        for field, value in (('summary', '  '), ('date_deadline', ''), ('date_deadline', '202610-10-10')):
            with self.subTest(field=field, value=value):
                self.assertEqual(self._post(field, value).status_code, 400)
        # An overdue activity re-saved with its own stored date is fine.
        self.activity.sudo().date_deadline = date.today() - timedelta(days=2)
        self.assertEqual(self._post('date_deadline', yesterday).status_code, 200)

    # -- UC-AC3 -----------------------------------------------------------
    def test_portal_user_forbidden(self):
        res = self._post('summary', 'Hijacked', login='pk_act_portal')
        self.assertEqual(res.status_code, 403)
        self.activity.invalidate_recordset()
        self.assertEqual(self.activity.summary, 'Call back')

    # -- UC-AC4 -----------------------------------------------------------
    def test_can_act_hook(self):
        kit_cls = type(self.env['portal.kit'])
        with patch.object(kit_cls, '_pk_activity_can_act', lambda self, activity: False):
            res = self._post('summary', 'Refused')
        self.assertEqual(res.status_code, 403)
        with patch.object(kit_cls, '_pk_activity_can_act', lambda self, activity: True):
            res = self._post('summary', 'Granted', login='pk_act_portal')
        self.assertEqual(res.status_code, 200, res.text)
        self.activity.invalidate_recordset()
        self.assertEqual(self.activity.summary, 'Granted')

    # -- UC-AC5 -----------------------------------------------------------
    def test_assignable_users_hook(self):
        kit_cls = type(self.env['portal.kit'])
        with patch.object(kit_cls, '_pk_activity_assignable_users', lambda self, activity: self.env.user):
            res = self._post('user_id', str(self.other.id))
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.json()['message'], 'You cannot assign this activity to that user.')
        with patch.object(kit_cls, '_pk_activity_assignable_users',
                          lambda self, activity: self.env['res.users'].browse(activity.env.ref('base.user_admin').id)):
            res = self._post('user_id', str(self.env.ref('base.user_admin').id))
            self.assertEqual(res.status_code, 200, res.text)
