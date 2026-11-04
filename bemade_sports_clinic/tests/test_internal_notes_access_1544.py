"""Task 1544 — injury internal notes are unreadable for coaches (AC1).

Use case: a portal coach has record access to the non-hidden injuries of
their teams. The injury's ``internal_notes`` are for treatment professionals
and staff only.

Acceptance criteria:
- A coach calling ``read`` / ``search_read`` on an injury of their team cannot
  get ``internal_notes`` — the ORM refuses (AccessError) or the field is absent
  (``fields_get`` does not list it), both in-process and through the JSON-RPC
  endpoint (``/web/dataset/call_kw``).
- A portal treatment professional and an internal user still read it.
- The coach sees no tracking value for ``internal_notes`` in the formatted
  chatter of the injury, and cannot read ``mail.tracking.value`` directly.

All fixtures are synthetic.
"""
import json

from odoo.addons.mail.tools.discuss import Store
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .portal_cov_common import PortalCovCommon

SECRET = 'ZZ-1544-internal-secret'


@tagged('-at_install', 'post_install')
class TestInternalNotesAccess1544(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Settle the fixture creation first: a record created in the same
        # transaction is not field-tracked until its create is finalized.
        cls.env.flush_all()
        cls.env.cr.precommit.run()
        cls.injury.write({'internal_notes': SECRET, 'external_notes': 'ZZ ext ok'})
        cls.internal = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZZ Internal', 'login': 'zz.internal.1544@example.com',
            'password': 'zz-internal-1544',
            'group_ids': [(6, 0, [
                cls.env.ref('bemade_sports_clinic.group_sports_clinic_admin').id])],
        })

    # -- ORM ---------------------------------------------------------------

    def test_coach_read_refused(self):
        injury = self.injury.with_user(self.coach)
        # The coach still reads the record itself (external fields).
        self.assertEqual(injury.read(['external_notes'])[0]['external_notes'], 'ZZ ext ok')
        with self.assertRaises(AccessError):
            injury.read(['internal_notes'])
        with self.assertRaises(AccessError):
            injury.search_read([('id', '=', self.injury.id)], ['internal_notes'])
        with self.assertRaises(AccessError):
            injury.invalidate_recordset()
            injury.internal_notes  # noqa: B018 — attribute access is the check

    def test_coach_default_read_omits_field(self):
        """The field is not advertised to a coach (the web client builds its
        field lists from fields_get), and other injury fields still read."""
        injury = self.injury.with_user(self.coach)
        self.assertNotIn('internal_notes', injury.fields_get())
        rows = injury.search_read(
            [('id', '=', self.injury.id)], ['diagnosis', 'external_notes', 'stage'])
        self.assertTrue(rows)
        self.assertNotIn(SECRET, json.dumps(rows, default=str))

    def test_coach_cannot_search_on_field(self):
        with self.assertRaises(AccessError):
            self.env['sports.patient.injury'].with_user(self.coach).search(
                [('internal_notes', 'ilike', 'ZZ-1544')])

    def test_tp_and_internal_still_read(self):
        self.assertEqual(
            self.injury.with_user(self.tp).read(['internal_notes'])[0]['internal_notes'],
            SECRET)
        self.assertEqual(
            self.injury.with_user(self.internal).read(
                ['internal_notes'])[0]['internal_notes'],
            SECRET)

    # -- JSON-RPC ----------------------------------------------------------

    def _call_kw(self, method, args, kwargs):
        resp = self.url_open(
            '/web/dataset/call_kw',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {
                'model': 'sports.patient.injury', 'method': method,
                'args': args, 'kwargs': kwargs,
            }}),
            headers={'Content-Type': 'application/json'},
        )
        return resp.json()

    @mute_logger('odoo.http')
    def test_coach_rpc_refused(self):
        self._login_coach()
        payload = self._call_kw(
            'search_read', [[('id', '=', self.injury.id)]], {'fields': ['internal_notes']})
        self.assertIn('error', payload)
        self.assertNotIn(SECRET, json.dumps(payload))
        payload = self._call_kw('read', [[self.injury.id], ['internal_notes']], {})
        self.assertIn('error', payload)
        self.assertNotIn(SECRET, json.dumps(payload))
        # No field list: whatever comes back (a core portal ACL error on
        # activity_ids today), the secret is not in it.
        payload = self._call_kw('search_read', [[('id', '=', self.injury.id)]], {})
        self.assertNotIn(SECRET, json.dumps(payload))

    def test_tp_rpc_allowed(self):
        self._login_tp()
        payload = self._call_kw(
            'search_read', [[('id', '=', self.injury.id)]], {'fields': ['internal_notes']})
        self.assertEqual(payload.get('result', [{}])[0].get('internal_notes'), SECRET)

    # -- Chatter tracking -----------------------------------------------------

    def _tracked_write(self):
        # Tracking is finalized at pre-commit: run it so the values exist
        # (the setUpClass write was settled with the creation, untracked).
        self.injury.write({'internal_notes': SECRET + ' v2'})
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _tracking_values(self):
        field = self.env['ir.model.fields']._get('sports.patient.injury', 'internal_notes')
        return self.env['mail.tracking.value'].sudo().search([
            ('field_id', '=', field.id),
            ('mail_message_id.model', '=', 'sports.patient.injury'),
            ('mail_message_id.res_id', '=', self.injury.id),
        ])

    def test_coach_sees_no_internal_notes_tracking(self):
        self._tracked_write()
        trackings = self._tracking_values()
        self.assertTrue(trackings, 'fixture: the internal-notes write must be tracked')
        # Core filter used by message formatting (Store) and message search.
        self.assertFalse(trackings._filter_has_field_access(self.env(user=self.coach)))
        self.assertEqual(
            trackings._filter_has_field_access(self.env(user=self.tp)), trackings)
        # Direct model access is refused for a coach.
        with self.assertRaises(AccessError):
            self.env['mail.tracking.value'].with_user(self.coach).search_count([])

    def test_formatted_chatter_has_no_secret_for_coach(self):
        # Whatever chatter messages the coach can see on the injury and the
        # patient, their formatted payload never carries the secret.
        self._tracked_write()
        for record in (self.injury, self.player):
            messages = self.env['mail.message'].with_user(self.coach).search([
                ('model', '=', record._name), ('res_id', '=', record.id)])
            store = Store()
            store.add(messages)
            self.assertNotIn(SECRET, json.dumps(store.get_result(), default=str))
        # Sanity: an internal clinic user's formatted chatter on the injury
        # DOES show it (so the check above would catch a leak).
        messages = self.env['mail.message'].with_user(self.internal).search([
            ('model', '=', 'sports.patient.injury'), ('res_id', '=', self.injury.id)])
        store = Store()
        store.add(messages)
        self.assertIn(SECRET, json.dumps(store.get_result(), default=str))
